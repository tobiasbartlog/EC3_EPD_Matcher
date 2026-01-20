"""EPD Matcher - Hauptprogramm."""
import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List

# UTF-8 Encoding für Konsolen-Output (wichtig bei Start von C#)
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import matching.prompt_builder
from matching.azure_matcher import AzureEPDMatcher
from utils.file_handler import load_json, save_json

def process_groups_batch(input_data: Dict[str, Any], matcher: AzureEPDMatcher) -> Dict[str, Any]:
    """Verarbeitet alle Gruppen mit Batch-Matching (1x Azure-Call für alle)."""
    if "Gruppen" not in input_data:
        print("Warnung: Keine 'Gruppen' in der Input-JSON gefunden.")
        return input_data

    output_data = input_data.copy()
    gruppen = output_data["Gruppen"]
    total = len(gruppen)

    print(f"\n{'=' * 70}")
    print(f"BATCH-MATCHING: {total} Schichten auf einmal")
    print(f"{'=' * 70}\n")

    # Sammle alle Materialien
    materials = []
    for gruppe in gruppen:
        materials.append({
            "material_name": gruppe.get("MATERIAL", ""),
            "context": {
                "NAME": gruppe.get("NAME", ""),
                "Volumen": gruppe.get("Volumen", 0),
                "GUID": gruppe.get("GUID", [])
            }
        })

    # Batch-Matching
    all_results = matcher.match_materials_batch(materials, max_results=10)

    # NEU: Hole Detail-Ergebnisse
    detailed_results = matcher.get_batch_detailed_results()

    # DEBUG
    print(f"\nDEBUG: detailed_results hat {len(detailed_results)} Schichten")
    for i, schicht in enumerate(detailed_results):
        print(f"  Schicht {i + 1}: {len(schicht)} Matches")
        if schicht:
            print(f"    Erstes Match: {schicht[0]}")

    # Ergebnisse zuordnen und ausgeben
    for idx, gruppe in enumerate(gruppen):
        print(f"\n{'=' * 70}")
        print(f"[{idx + 1}/{total}] {gruppe.get('NAME', 'Unbekannt')}")
        print(f"{'=' * 70}")
        print(f"Material: {gruppe.get('MATERIAL', '')}")

        if idx < len(all_results):
            result = all_results[idx]
            matched_ids = result.get("ids", [])
            matched_ids = remove_duplicates(matched_ids)

            gruppe["id"] = matched_ids
            gruppe["id_confidence"] = result.get("confidence", {})

            # NEU: Zeige Details
            if idx < len(detailed_results):
                matches = detailed_results[idx]
                print(f"\n🎯 {len(matches)} Matches gefunden:\n")

                for i, match in enumerate(matches[:10], 1):
                    match_id = match.get("uuid", "N/A")
                    name = match.get("name", "Unbekannt")
                    conf = match.get("confidence")
                    reason = match.get("begruendung", "Keine Begründung")

                    if conf is not None:
                        if conf >= 85:
                            conf_icon = "🟢"
                        elif conf >= 60:
                            conf_icon = "🟡"
                        else:
                            conf_icon = "🟠"
                        conf_str = f"{conf_icon} {conf}%"
                    else:
                        conf_str = "❓ N/A"

                    print(f"{i:2d}. ID: {match_id}")
                    print(f"    Name: {name}")
                    print(f"    Confidence: {conf_str}")
                    print(f"    Begründung: {reason}")
                    print()

            print(f"→ {len(matched_ids)} ID(s) in Output geschrieben")
        else:
            gruppe["id"] = []
            gruppe["id_confidence"] = {}

    return output_data


def process_groups(input_data: Dict[str, Any], matcher: AzureEPDMatcher) -> Dict[str, Any]:
    """
    Verarbeitet alle Gruppen einzeln (Legacy-Modus, 1 Azure-Call pro Schicht).

    Args:
        input_data: Input-JSON mit Gruppen
        matcher: Initialisierter EPD-Matcher

    Returns:
        Verarbeitete Daten mit hinzugefügten IDs und Confidence-Werten
    """
    if "Gruppen" not in input_data:
        print("Warnung: Keine 'Gruppen' in der Input-JSON gefunden.")
        return input_data

    output_data = input_data.copy()
    total_groups = len(output_data["Gruppen"])

    for idx, gruppe in enumerate(output_data["Gruppen"], 1):
        process_single_group(gruppe, idx, total_groups, matcher)

    return output_data


def process_single_group(
    gruppe: Dict[str, Any],
    index: int,
    total: int,
    matcher: AzureEPDMatcher
) -> None:
    """
    Verarbeitet eine einzelne Gruppe.

    Args:
        gruppe: Gruppen-Dictionary (wird in-place modifiziert)
        index: Aktueller Index
        total: Gesamt-Anzahl Gruppen
        matcher: EPD-Matcher Instanz
    """
    material = gruppe.get("MATERIAL", "")

    print(f"[{index}/{total}] Verarbeite: {gruppe.get('NAME', 'Unbekannt')}")
    print(f"  Material: {material}")

    # Kontext für besseres Matching
    context = {
        "NAME": gruppe.get("NAME", ""),
        "Volumen": gruppe.get("Volumen", 0),
        "GUID": gruppe.get("GUID", [])
    }

    # Azure OpenAI Matching
    matched_ids = matcher.match_material(
        material_name=material,
        context=context,
        max_results=10
    )

    # Duplikate entfernen (behält Reihenfolge)
    matched_ids = remove_duplicates(matched_ids)

    # Ergebnisse zur Gruppe hinzufügen
    gruppe["id"] = matched_ids
    gruppe["id_confidence"] = build_confidence_map(matched_ids, matcher)

    print(f"  → {len(matched_ids)} ID(s) gefunden\n")


def remove_duplicates(ids: list) -> list:
    """Entfernt Duplikate aus Liste unter Beibehaltung der Reihenfolge."""
    seen = set()
    return [x for x in ids if not (str(x) in seen or seen.add(str(x)))]


def build_confidence_map(
    matched_ids: list,
    matcher: AzureEPDMatcher
) -> Dict[str, int]:
    """
    Erstellt Mapping von ID zu Confidence-Wert.

    Args:
        matched_ids: Liste der gematchten IDs
        matcher: Matcher-Instanz mit letzten Ergebnissen

    Returns:
        Dictionary {id: confidence}
    """
    detailed_results = matcher.get_last_results()
    matched_set = {str(x) for x in matched_ids}

    return {
        str(result["uuid"]): result["confidence"]
        for result in detailed_results
        if str(result["uuid"]) in matched_set
    }


def parse_arguments() -> argparse.Namespace:
    """Parst Kommandozeilen-Argumente."""
    parser = argparse.ArgumentParser(
        description='EPD Matcher - Verarbeitet Bauschichten und fügt IDs hinzu'
    )
    parser.add_argument(
        'id_folder',
        type=str,
        help='Pfad zum ID-Ordner (enthält input und output Unterordner)'
    )
    parser.add_argument(
        '--input-file',
        type=str,
        default='input.json',
        help='Name der Input-JSON-Datei (Standard: input.json)'
    )
    parser.add_argument(
        '--output-file',
        type=str,
        default='output.json',
        help='Name der Output-JSON-Datei (Standard: output.json)'
    )
    parser.add_argument(
        '--no-batch',
        action='store_true',
        help='Deaktiviert Batch-Matching (jede Schicht einzeln)'
    )
    return parser.parse_args()


def main():
    """Hauptfunktion des Skripts."""
    args = parse_arguments()

    # Pfade konstruieren
    id_folder = Path(args.id_folder)
    input_path = id_folder / "input" / args.input_file
    output_path = id_folder / "output" / args.output_file

    # Header ausgeben
    print("=" * 60)
    print("EPD MATCHER - Azure OpenAI Edition")
    print("=" * 60)
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    if not args.no_batch:
        print("Mode:   BATCH (alle Schichten in 1 Request) ⚡")
    else:
        print("Mode:   EINZELN (1 Request pro Schicht)")
    print("=" * 60 + "\n")

    # Input-Ordner prüfen
    if not input_path.parent.exists():
        print(f"Fehler: Input-Ordner existiert nicht: {input_path.parent}")
        sys.exit(1)

    # Matcher initialisieren
    try:
        matcher = AzureEPDMatcher()
    except ValueError as e:
        print(f"Fehler: {e}")
        sys.exit(1)

    # Input laden
    input_data = load_json(input_path)
    print(f"✓ Input geladen: {len(input_data.get('Gruppen', []))} Gruppe(n)\n")

    # Verarbeitung durchführen (Batch oder Einzeln)
    if args.no_batch:
        output_data = process_groups(input_data, matcher)
    else:
        output_data = process_groups_batch(input_data, matcher)

    # Output speichern
    save_json(output_data, output_path)

    # Footer ausgeben
    print("\n" + "=" * 60)
    print("VERARBEITUNG ABGESCHLOSSEN")
    print("=" * 60)


if __name__ == "__main__":
    main()
