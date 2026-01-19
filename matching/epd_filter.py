"""
EPD-Vorfilterung für effizienteres Matching.

Dieses Modul filtert EPDs VOR dem GPT-Call basierend auf:
1. Asphalt-Typ (AC, SMA, MA, PA)
2. Schicht-Code (D, B, T)
3. Ausschluss-Begriffe

Vorteile:
- ~80% weniger Tokens pro Request
- Höhere Matching-Qualität (GPT sieht nur relevante EPDs)
- Schneller + günstiger

Verwendung:
    from matching.epd_filter import EPDFilter

    filter = EPDFilter()
    filtered_epds = filter.filter_for_materials(all_epds, materials)
"""

from typing import Dict, Any, List, Optional, Tuple
from utils.asphalt_glossar import (
    parse_material_input,
    filter_epds_for_material,
    ASPHALT_TYPES,
    LAYER_CODES,
    AUSSCHLUSS_BEGRIFFE
)


class EPDFilter:
    """Filtert EPDs basierend auf Material-Analyse."""

    def __init__(self, max_epds_per_material: int = 100, debug: bool = False):
        """
        Args:
            max_epds_per_material: Maximale EPDs pro Material nach Filterung
            debug: Debug-Output aktivieren
        """
        self.max_epds = max_epds_per_material
        self.debug = debug

    def filter_for_materials(
            self,
            all_epds: List[Dict[str, Any]],
            materials: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Filtert EPDs für mehrere Materialien.

        Args:
            all_epds: Alle verfügbaren EPDs
            materials: Liste von Material-Dicts mit keys: material_name, context

        Returns:
            Dict mit:
            - combined_epds: Vereinigte EPD-Liste für alle Materialien
            - per_material: Dict mit EPDs pro Material-Index
            - stats: Statistiken zur Filterung
        """
        all_relevant_ids = set()
        per_material = {}
        stats = {
            "total_epds": len(all_epds),
            "materials_count": len(materials),
            "filtered_per_material": []
        }

        for idx, mat in enumerate(materials):
            material_name = mat.get("material_name", "")
            schicht_name = mat.get("context", {}).get("NAME", "")

            # Parse Material
            parsed = parse_material_input(material_name, schicht_name)

            # Filtere EPDs
            primaer, sekundaer = filter_epds_for_material(
                all_epds, parsed, self.max_epds
            )

            # Speichere Ergebnisse
            combined = primaer + sekundaer
            per_material[idx] = {
                "parsed": parsed,
                "primaer": primaer,
                "sekundaer": sekundaer,
                "combined": combined
            }

            # Sammle alle relevanten IDs
            for epd in combined:
                all_relevant_ids.add(epd.get("id"))

            # Stats
            stats["filtered_per_material"].append({
                "material": material_name,
                "schicht": schicht_name,
                "primaer_count": len(primaer),
                "sekundaer_count": len(sekundaer),
                "total_filtered": len(combined)
            })

            if self.debug:
                print(f"  Material {idx + 1}: {material_name}")
                print(f"    Parsed: {parsed.get('typ', 'N/A')} / {parsed.get('schicht', 'N/A')}")
                print(f"    Primär: {len(primaer)}, Sekundär: {len(sekundaer)}")

        # Kombinierte EPD-Liste erstellen (keine Duplikate)
        combined_epds = [epd for epd in all_epds if epd.get("id") in all_relevant_ids]

        stats["combined_count"] = len(combined_epds)
        stats["reduction_percent"] = round(
            (1 - len(combined_epds) / len(all_epds)) * 100, 1
        ) if all_epds else 0

        if self.debug:
            print(f"\n  Gesamt: {len(all_epds)} → {len(combined_epds)} EPDs ({stats['reduction_percent']}% Reduktion)")

        return {
            "combined_epds": combined_epds,
            "per_material": per_material,
            "stats": stats
        }

    def filter_for_single_material(
            self,
            all_epds: List[Dict[str, Any]],
            material_name: str,
            schicht_name: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Filtert EPDs für ein einzelnes Material.

        Args:
            all_epds: Alle verfügbaren EPDs
            material_name: Material-Bezeichnung
            schicht_name: Optionaler Schichtname aus IFC

        Returns:
            Tuple: (gefilterte_epds, parsed_material)
        """
        parsed = parse_material_input(material_name, schicht_name)
        primaer, sekundaer = filter_epds_for_material(all_epds, parsed, self.max_epds)

        return primaer + sekundaer, parsed

    @staticmethod
    def get_filter_summary(stats: Dict[str, Any]) -> str:
        """Generiert lesbare Zusammenfassung der Filterung."""
        lines = [
            f"EPD-Filterung: {stats['total_epds']} → {stats['combined_count']} EPDs",
            f"Reduktion: {stats['reduction_percent']}%",
            f"Materialien: {stats['materials_count']}",
            ""
        ]

        for i, mat_stat in enumerate(stats.get("filtered_per_material", []), 1):
            lines.append(
                f"  {i}. {mat_stat['material'][:40]}... → "
                f"{mat_stat['primaer_count']} primär, {mat_stat['sekundaer_count']} sekundär"
            )

        return "\n".join(lines)


# =============================================================================
# CONFIDENCE-VALIDATOR (Nachvalidierung der GPT-Ergebnisse)
# =============================================================================

class ConfidenceValidator:
    """Validiert und korrigiert GPT-Confidence-Werte basierend auf Regeln."""

    @staticmethod
    def validate_match(
            epd: Dict[str, Any],
            parsed_material: Dict[str, Any],
            gpt_confidence: int
    ) -> Tuple[int, str]:
        """
        Validiert einen einzelnen Match und korrigiert Confidence wenn nötig.

        Args:
            epd: EPD-Eintrag
            parsed_material: Parsed Material-Info
            gpt_confidence: Von GPT vorgeschlagene Confidence

        Returns:
            Tuple: (korrigierte_confidence, grund)
        """
        epd_name = epd.get("name", "").lower()
        epd_klassifizierung = epd.get("klassifizierung", "").lower()
        combined = f"{epd_name} {epd_klassifizierung}"

        # 1. Ausschluss-Check
        for excl in AUSSCHLUSS_BEGRIFFE:
            if excl.lower() in combined:
                return min(gpt_confidence, 25), f"Ausschluss-Begriff '{excl}' gefunden"

        # 2. Schicht-Check (wenn Material eine Schicht hat)
        schicht_muss = parsed_material.get("schicht_epd_muss_enthalten", "")
        if schicht_muss:
            schicht_muss_lower = schicht_muss.lower()
            if schicht_muss_lower not in combined:
                # Falscher Schichttyp
                return min(gpt_confidence, 45), f"Schicht-Begriff '{schicht_muss}' fehlt im EPD-Namen"

        # 3. Typ-Check
        ist_asphalt = any(
            keyword.lower() in combined
            for keyword in ["asphalt", "bitumen", "bituminös"]
        )
        if parsed_material.get("ist_asphalt") and not ist_asphalt:
            return min(gpt_confidence, 35), "Kein Asphalt-Bezug im EPD"

        # Alles ok
        return gpt_confidence, "Validiert"

    @staticmethod
    def validate_batch_results(
            matches_per_schicht: List[List[Dict[str, Any]]],
            materials: List[Dict[str, Any]],
            epds: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Validiert alle Batch-Ergebnisse.

        Args:
            matches_per_schicht: GPT-Matches pro Schicht
            materials: Original-Materialien
            epds: EPD-Liste (für Name-Lookup)

        Returns:
            Korrigierte Matches pro Schicht
        """
        # EPD-Lookup erstellen
        epd_by_id = {str(e.get("id")): e for e in epds}

        validated_results = []

        for schicht_idx, matches in enumerate(matches_per_schicht):
            material = materials[schicht_idx] if schicht_idx < len(materials) else {}
            material_name = material.get("material_name", "")
            schicht_name = material.get("context", {}).get("NAME", "")

            # Parse Material
            parsed = parse_material_input(material_name, schicht_name)

            validated_matches = []
            for match in matches:
                epd_id = str(match.get("uuid", ""))
                epd = epd_by_id.get(epd_id, {})
                gpt_confidence = match.get("confidence", 50)

                # Validiere
                new_confidence, grund = ConfidenceValidator.validate_match(
                    epd, parsed, gpt_confidence
                )

                validated_match = match.copy()
                validated_match["confidence"] = new_confidence

                # Füge Validierungs-Info hinzu wenn geändert
                if new_confidence != gpt_confidence:
                    original_reason = match.get("begruendung", "")
                    validated_match["begruendung"] = f"{original_reason} [Korrigiert: {grund}]"
                    validated_match["confidence_original"] = gpt_confidence

                validated_matches.append(validated_match)

            # Neu sortieren nach korrigierter Confidence
            validated_matches.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            validated_results.append(validated_matches)

        return validated_results


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("EPD-FILTER TEST")
    print("=" * 70)

    # Simulierte EPDs
    test_epds = [
        {"id": 1, "name": "Asphaltdeckschicht nach TL Asphalt", "klassifizierung": "Straßenbau"},
        {"id": 2, "name": "Asphaltbinder für Bundesstraßen", "klassifizierung": "Straßenbau"},
        {"id": 3, "name": "Asphalttragschicht Standard", "klassifizierung": "Straßenbau"},
        {"id": 4, "name": "Betonpflaster grau", "klassifizierung": "Pflaster"},
        {"id": 5, "name": "Splittmastixasphalt SMA", "klassifizierung": "Straßenbau"},
        {"id": 6, "name": "Gussasphalt für Brücken", "klassifizierung": "Brückenbau"},
        {"id": 7, "name": "Zement CEM I", "klassifizierung": "Bindemittel"},
    ]

    # Simulierte Materialien
    test_materials = [
        {
            "material_name": "Aspahltbeton",  # Tippfehler!
            "context": {"NAME": "Deckschicht"}
        },
        {
            "material_name": "AC 16 B S",
            "context": {"NAME": "Binderschicht"}
        }
    ]

    # Filter testen
    filter = EPDFilter(max_epds_per_material=50, debug=True)

    print("\nFilterung:")
    result = filter.filter_for_materials(test_epds, test_materials)

    print("\n" + filter.get_filter_summary(result["stats"]))

    print("\n\nGefilterte EPDs:")
    for epd in result["combined_epds"]:
        print(f"  - {epd['id']}: {epd['name']}")