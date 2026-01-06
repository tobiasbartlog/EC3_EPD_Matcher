import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any



# Importiere das Azure Matching-Modul
from src.old.onlinezugang import get_matcher

def load_input_json(input_path: Path) -> Dict[str, Any]:
    """Lädt die Input-JSON-Datei."""
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Fehler: Input-Datei nicht gefunden: {input_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Fehler: Ungültige JSON-Datei: {e}")
        sys.exit(1)


def process_groups(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verarbeitet die Gruppen und fügt id-Einträge hinzu.
    """
    output_data = input_data.copy()

    if "Gruppen" not in output_data:
        print("Warnung: Keine 'Gruppen' in der Input-JSON gefunden.")
        return output_data

    # Azure Matcher initialisieren (Singleton - wird nur einmal erstellt)
    try:
        matcher = get_matcher()
    except ValueError as e:
        print(f"Fehler: {e}")
        sys.exit(1)

    total_groups = len(output_data["Gruppen"])

    for idx, gruppe in enumerate(output_data["Gruppen"], 1):
        material = gruppe.get("MATERIAL", "")

        print(f"[{idx}/{total_groups}] Verarbeite: {gruppe.get('NAME', 'Unbekannt')}")
        print(f"  Material: {material}")

        # Kontext für besseres Matching erstellen
        context = {
            "NAME": gruppe.get("NAME", ""),
            "Volumen": gruppe.get("Volumen", 0),
            "GUID": gruppe.get("GUID", [])
        }

        # Azure OpenAI Matching durchführen
        matched_ids = matcher.match_material(
            material_name=material,
            context=context,
            max_results=10
        )

        # IDs hinzufügen
        seen = set() # TEST
        matched_ids = [x for x in matched_ids if not (str(x) in seen or seen.add(str(x)))] # TEST
        gruppe["id"] = matched_ids


        # print(f"  → {len(matched_uuids)} UUID(s) gefunden\n")
        print(f"  → {len(matched_ids)} ID(s) gefunden\n")

        detailed = matcher.get_last_results()

        # Map ID → Confidence (nur für die zurückgegebenen IDs)
        conf_map = {}
        # Dieselben Top-N wie matched_ids
        top_set = set(str(x) for x in matched_ids)
        for m in detailed:
            uid = str(m.get("uuid", ""))
            if uid in top_set:
                conf_map[uid] = m.get("confidence")

        # In die Gruppe schreiben:
        gruppe["id_confidence"] = conf_map  # Zuordnung ID → Confidence


    return output_data


def save_output_json(output_data: Dict[str, Any], output_path: Path) -> None:
    """Speichert die Output-JSON-Datei."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"✓ Output erfolgreich gespeichert: {output_path}")
    except Exception as e:
        print(f"Fehler beim Speichern der Output-Datei: {e}")
        sys.exit(1)


def main():
    """Hauptfunktion des Skripts."""
    parser = argparse.ArgumentParser(
        # description='EPD Matcher - Verarbeitet Bauschichten und fügt Baudat-UUIDs hinzu'
        description='EPD Matcher - Verarbeitet Bauschichten und fügt IDs hinzu' #TEST
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

    args = parser.parse_args()

    # Pfade konstruieren
    id_folder = Path(args.id_folder)
    input_folder = id_folder / "input"
    output_folder = id_folder / "output"

    input_path = input_folder / args.input_file
    output_path = output_folder / args.output_file

    print("=" * 60)
    print("EPD MATCHER - Azure OpenAI Edition")
    print("=" * 60)
    print(f"ID-Ordner:     {id_folder}")
    print(f"Input-Ordner:  {input_folder}")
    print(f"Output-Ordner: {output_folder}")
    print("=" * 60 + "\n")

    # Prüfen ob Input-Ordner existiert
    if not input_folder.exists():
        print(f"Fehler: Input-Ordner existiert nicht: {input_folder}")
        sys.exit(1)

    # JSON laden
    input_data = load_input_json(input_path)
    print(f"✓ Input-Datei geladen: {len(input_data.get('Gruppen', []))} Gruppe(n) gefunden\n")

    # Verarbeitung durchführen
    output_data = process_groups(input_data)

    # Output speichern
    save_output_json(output_data, output_path)

    print("\n" + "=" * 60)
    print("VERARBEITUNG ABGESCHLOSSEN")
    print("=" * 60)


if __name__ == "__main__":
    main()
