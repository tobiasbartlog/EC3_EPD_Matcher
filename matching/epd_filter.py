"""
EPD-Vorfilterung für effizienteres Matching.

Stage 3: Pre-filtering
Stage 5: Confidence Validation
"""

from typing import Dict, Any, List, Optional, Tuple

from config.settings import ValidationConfig, GlossarConfig
from utils.asphalt_glossar import (
    parse_material_input,
    filter_epds_for_material,
    ASPHALT_TYPES,
    LAYER_CODES,
    AUSSCHLUSS_BEGRIFFE
)


class EPDFilter:
    """Stage 3: Filtert EPDs basierend auf Material-Analyse."""

    def __init__(self, max_epds_per_material: int = 100, debug: bool = False):
        self.max_epds = max_epds_per_material
        self.debug = debug

    def filter_for_materials(
            self,
            all_epds: List[Dict[str, Any]],
            materials: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Filtert EPDs für mehrere Materialien."""
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

            parsed = parse_material_input(material_name, schicht_name)
            primaer, sekundaer = filter_epds_for_material(
                all_epds, parsed, self.max_epds
            )

            combined = primaer + sekundaer
            per_material[idx] = {
                "parsed": parsed,
                "primaer": primaer,
                "sekundaer": sekundaer,
                "combined": combined
            }

            for epd in combined:
                all_relevant_ids.add(epd.get("id"))

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
        """Filtert EPDs für ein einzelnes Material."""
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
# STAGE 5: CONFIDENCE-VALIDATOR
# =============================================================================

# Begriffe die für bestimmte Materialtypen NICHT passen
MATERIAL_MISMATCHES: Dict[str, List[str]] = {
    "asphalt": [
        "bitumenbahn", "bitumenbahnen", "dachbahn", "dachabdichtung",
        "schweißbahn", "kaltselbstklebebahn", "dampfsperre",
        "emulsion",
    ],
    "schotter": [
        "bitumenbahn", "bitumenbahnen", "asphalt", "gussasphalt",
        "emulsion", "dampfsperre",
    ],
    "daemmung": [
        "bitumenbahn", "bitumenbahnen", "asphalt", "gussasphalt",
        "schotter", "kies", "splitt", "emulsion",
    ],
}


class ConfidenceValidator:
    """Stage 5: Validiert und korrigiert GPT-Confidence-Werte."""

    @staticmethod
    def validate_match(
            epd: Dict[str, Any],
            parsed_material: Dict[str, Any],
            gpt_confidence: int
    ) -> Tuple[int, str]:
        """
        Validiert einen einzelnen Match und korrigiert Confidence wenn nötig.

        Verwendet ValidationConfig für Schwellwerte.
        """
        epd_name = epd.get("name", "").lower()
        epd_klassifizierung = epd.get("klassifizierung", "").lower()
        combined = f"{epd_name} {epd_klassifizierung}"

        max_excluded = ValidationConfig.MAX_CONFIDENCE_EXCLUDED

        # 1. Ausschluss-Check
        for excl in AUSSCHLUSS_BEGRIFFE:
            if excl.lower() in combined:
                return min(gpt_confidence, max_excluded), f"Ausschluss-Begriff '{excl}' gefunden"

        # 2. Material-Typ-Mismatch Check
        material_type = ConfidenceValidator._get_material_type(parsed_material)
        if material_type:
            mismatches = MATERIAL_MISMATCHES.get(material_type, [])
            for mismatch in mismatches:
                if mismatch in combined:
                    return min(gpt_confidence, max_excluded), f"'{mismatch}' passt nicht zu {material_type}"

        # 3. Schicht-Check
        schicht_muss = parsed_material.get("schicht_epd_muss_enthalten", "")
        if schicht_muss:
            schicht_muss_lower = schicht_muss.lower()
            if schicht_muss_lower not in combined:
                ist_gleicher_typ = ConfidenceValidator._ist_gleicher_material_typ(
                    combined, parsed_material
                )
                if ist_gleicher_typ:
                    return min(gpt_confidence, 60), f"Schicht-Begriff '{schicht_muss}' fehlt"
                else:
                    return min(gpt_confidence, 35), f"Schicht-Begriff '{schicht_muss}' fehlt + falscher Typ"

        # 4. Typ-Check für Asphalt
        ist_asphalt = any(
            keyword.lower() in combined
            for keyword in ["asphalt", "bitumen", "bituminös"]
        )
        if parsed_material.get("ist_asphalt") and not ist_asphalt:
            return min(gpt_confidence, 35), "Kein Asphalt-Bezug im EPD"

        return gpt_confidence, "Validiert"

    @staticmethod
    def _get_material_type(parsed_material: Dict[str, Any]) -> Optional[str]:
        """Ermittelt den Material-Typ für Mismatch-Prüfung."""
        material_orig = parsed_material.get("material_original", "").lower()
        schicht_orig = parsed_material.get("schicht_name_original", "").lower()
        combined = f"{material_orig} {schicht_orig}"

        if parsed_material.get("ist_asphalt"):
            return "asphalt"
        if any(kw in combined for kw in ["schotter", "kies", "splitt", "frostschutz"]):
            return "schotter"
        if any(kw in combined for kw in ["dämm", "xps", "eps", "pur", "pir", "mineralwolle"]):
            return "daemmung"
        return None

    @staticmethod
    def _ist_gleicher_material_typ(epd_combined: str, parsed_material: Dict[str, Any]) -> bool:
        """Prüft ob EPD und Material grundsätzlich gleicher Typ sind."""
        if parsed_material.get("ist_asphalt"):
            return any(kw in epd_combined for kw in ["asphalt", "bituminös"])
        return False

    @staticmethod
    def validate_batch_results(
            matches_per_schicht: List[List[Dict[str, Any]]],
            materials: List[Dict[str, Any]],
            epds: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Validiert alle Batch-Ergebnisse.

        Filtert Ergebnisse unter MIN_CONFIDENCE raus.
        """
        epd_by_id = {str(e.get("id")): e for e in epds}
        min_confidence = ValidationConfig.MIN_CONFIDENCE

        validated_results = []

        for schicht_idx, matches in enumerate(matches_per_schicht):
            material = materials[schicht_idx] if schicht_idx < len(materials) else {}
            material_name = material.get("material_name", "")
            schicht_name = material.get("context", {}).get("NAME", "")

            parsed = parse_material_input(material_name, schicht_name)

            validated_matches = []
            for match in matches:
                epd_id = str(match.get("uuid", ""))
                epd = epd_by_id.get(epd_id, {})
                gpt_confidence = match.get("confidence", 50)

                new_confidence, grund = ConfidenceValidator.validate_match(
                    epd, parsed, gpt_confidence
                )

                # Filter by MIN_CONFIDENCE
                if new_confidence < min_confidence:
                    continue

                validated_match = match.copy()
                validated_match["confidence"] = new_confidence

                if new_confidence != gpt_confidence:
                    original_reason = match.get("begruendung", "")
                    validated_match["begruendung"] = f"{original_reason} [Korrigiert: {grund}]"
                    validated_match["confidence_original"] = gpt_confidence

                validated_matches.append(validated_match)

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
    print(f"ValidationConfig.MIN_CONFIDENCE: {ValidationConfig.MIN_CONFIDENCE}")
    print(f"ValidationConfig.MAX_CONFIDENCE_EXCLUDED: {ValidationConfig.MAX_CONFIDENCE_EXCLUDED}")

    test_cases = [
        ("Bitumenbahnen G 200 S4", "AC 16 D S", "Deckschicht", "sollte niedrig sein"),
        ("Asphalttragschicht", "AC 16 D S", "Deckschicht", "sollte mittel sein"),
        ("Asphaltdeckschicht", "AC 16 D S", "Deckschicht", "sollte hoch sein"),
    ]

    for epd_name, material, schicht, erwartung in test_cases:
        epd = {"name": epd_name, "klassifizierung": ""}
        parsed = parse_material_input(material, schicht)
        new_conf, grund = ConfidenceValidator.validate_match(epd, parsed, 85)
        print(f"\nEPD: {epd_name} → {new_conf}% ({grund})")