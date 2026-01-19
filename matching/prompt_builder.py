"""Prompt-Generierung für EPD-Matching."""
from typing import Dict, Any, List, Optional

from config.settings import MatchingConfig

# Import des Asphalt-Glossars (ACHTUNG: Dateiname muss asphalt_glossar.py sein!)
from utils.asphalt_glossar import (
    generate_prompt_glossary,
    generate_material_context,
    parse_material_input,
    filter_epds_for_material,
    AUSSCHLUSS_BEGRIFFE
)


class PromptBuilder:
    """Erstellt strukturierte Prompts für Azure OpenAI."""

    @staticmethod
    def build_batch_matching_prompt(
        materials: List[Dict[str, Any]],
        epds: List[Dict[str, Any]],
        max_results: int = 10
    ) -> str:
        """
        Erstellt Prompt für MEHRERE Materialien auf einmal (Batch).

        Args:
            materials: Liste von Material-Dicts mit keys: material_name, context
            epds: Liste verfügbarer EPD-Einträge
            max_results: Maximale Anzahl Ergebnisse pro Material

        Returns:
            Formatierter Prompt-String
        """
        sections = [
            PromptBuilder._build_batch_header(materials),
            PromptBuilder._build_epd_list(epds),
            PromptBuilder._build_batch_task_section(materials, max_results)
        ]

        return "\n".join(s for s in sections if s)

    @staticmethod
    def build_matching_prompt(
        material_name: str,
        epds: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        max_results: int = 10
    ) -> str:
        """
        Erstellt Prompt für EINZELNES Material.

        Args:
            material_name: Name des zu matchenden Materials
            epds: Liste verfügbarer EPD-Einträge
            context: Zusätzlicher Kontext (NAME, Volumen, GUID)
            max_results: Maximale Anzahl Ergebnisse

        Returns:
            Formatierter Prompt-String
        """
        sections = [
            PromptBuilder._build_header(material_name, context),
            PromptBuilder._build_context_section(context),
            PromptBuilder._build_epd_list(epds),
            PromptBuilder._build_task_section(material_name, context, max_results)
        ]

        return "\n".join(s for s in sections if s)

    @staticmethod
    def _build_batch_header(materials: List[Dict[str, Any]]) -> str:
        """Erstellt Header für Batch-Matching mit parsed Material-Kontext."""
        header = f"Baumaterial-Matching (Batch: {len(materials)} Schichten)\n\n"

        for i, mat in enumerate(materials, 1):
            material_name = mat.get("material_name", "Unbekannt")
            context = mat.get("context", {})
            schicht_name = context.get("NAME", "")

            # Schichtname VOR Material nennen
            if schicht_name:
                header += f"SCHICHT {i}: {schicht_name}\n"
                header += f"  Material: {material_name}\n"
            else:
                header += f"SCHICHT {i}: \"{material_name}\"\n"

            # Parsed Material-Kontext (nutzt jetzt Fallback!)
            parsed_context = generate_material_context(material_name, schicht_name)
            header += f"  → Parsed: {parsed_context}\n"

            if context:
                if context.get("Volumen"):
                    header += f"  - Volumen: {context['Volumen']} m³\n"
                if context.get("GUID"):
                    header += f"  - IFC GUIDs: {len(context['GUID'])} Elemente\n"

            header += "\n"

        return header

    @staticmethod
    def _build_header(material_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Erstellt Prompt-Header für Einzelmaterial."""
        schicht_name = context.get("NAME", "") if context else ""

        header = "Baumaterial-Matching\n\n"

        if schicht_name:
            header += f"Schicht: {schicht_name}\n"

        header += f'Material: "{material_name}"\n'

        # Parsed Kontext mit Fallback
        parsed_context = generate_material_context(material_name, schicht_name)
        header += f"→ Parsed: {parsed_context}\n"

        return header

    @staticmethod
    def _build_context_section(context: Optional[Dict[str, Any]]) -> str:
        """Erstellt Kontext-Sektion wenn vorhanden."""
        if not context:
            return ""

        lines = []
        if context.get("Volumen"):
            lines.append(f"- Volumen: {context['Volumen']} m³")
        if context.get("GUID"):
            lines.append(f"- IFC GUIDs: {len(context['GUID'])} Elemente")

        if not lines:
            return ""

        return "\nZusätzlicher Kontext:\n" + "\n".join(lines)

    @staticmethod
    def _build_epd_list(epds: List[Dict[str, Any]]) -> str:
        """
        Erstellt formatierte EPD-Liste.
        Modus hängt von MatchingConfig.USE_DETAIL_MATCHING ab.
        """
        header = f"\n{'='*70}\nVERFÜGBARE EPD-EINTRÄGE ({len(epds)})\n{'='*70}"

        if MatchingConfig.USE_DETAIL_MATCHING:
            # Detail-Modus
            entries = []
            for i, epd in enumerate(epds, 1):
                epd_id = epd.get("id")
                name = str(epd.get("name", "N/A"))[:200]
                klassifizierung = str(epd.get("klassifizierung", ""))[:150]

                entry_lines = [
                    f"\n{i}. ID: {epd_id}",
                    f"   Name: {name}"
                ]

                if klassifizierung:
                    entry_lines.append(f"   Klassifizierung: {klassifizierung}")

                tech_desc = str(epd.get("technischeBeschreibung", ""))[:300]
                if tech_desc:
                    entry_lines.append(f"   Technische Beschreibung: {tech_desc}...")

                anmerkungen = str(epd.get("anmerkungen", ""))[:250]
                if anmerkungen:
                    entry_lines.append(f"   Anmerkungen: {anmerkungen}...")

                entries.append("\n".join(entry_lines))
        else:
            # Namen-Modus (kompakt)
            entries = []
            for i, epd in enumerate(epds, 1):
                epd_id = epd.get("id")
                name = str(epd.get("name", "N/A"))
                entries.append(f"{i}. ID: {epd_id} | Name: {name}")

        return header + "\n" + "\n".join(entries)

    @staticmethod
    def _get_material_glossary() -> str:
        """Gibt das Asphalt-Glossar für den Prompt zurück."""
        return generate_prompt_glossary()

    @staticmethod
    def _get_ausschluss_liste_kompakt() -> str:
        """Gibt kompakte Ausschluss-Liste zurück."""
        return ", ".join(AUSSCHLUSS_BEGRIFFE[:15])

    @staticmethod
    def _build_batch_task_section(materials: List[Dict[str, Any]], max_results: int) -> str:
        """Erstellt Aufgabenstellung für Batch-Matching."""

        # Material-Liste mit parsed Kontext
        material_lines = []
        for i, mat in enumerate(materials, 1):
            mat_name = mat.get('material_name', 'Unbekannt')
            context = mat.get('context', {})
            context_name = context.get('NAME', 'Unbekannt')

            # Parse mit Fallback auf Schichtname!
            parsed = parse_material_input(mat_name, context_name)

            line = f"  - SCHICHT {i} ({context_name}): \"{mat_name}\""

            if parsed.get("schicht") and parsed.get("schicht_epd_muss_enthalten"):
                schicht_info = parsed.get("schicht_epd_muss_enthalten", "")
                line += f"\n    → Schicht {parsed['schicht']}: EPD muss \"{schicht_info}\" enthalten!"
            elif parsed.get("ist_asphalt"):
                line += f"\n    → Asphalt erkannt, aber kein Schichtcode gefunden"

            material_lines.append(line)

        material_list = "\n".join(material_lines)
        glossary = PromptBuilder._get_material_glossary()

        if MatchingConfig.USE_DETAIL_MATCHING:
            criteria = f"""{glossary}

Bewertungskriterien:
- Verwende nur die oben gelisteten EPD-Einträge
- PFLICHT: Nutze das Glossar für EXAKTE Interpretation!
- ⚠️ SCHICHTCODE-MATCHING IST PFLICHT! EPD-Name muss korrekten Schicht-Begriff enthalten!
- Nutze ALLE EPD-Felder (Name, Klassifizierung, Beschreibung, Anmerkungen)
- Gib eine kurze Begründung mit konkreten Zitaten
- Liefere Confidence-Score in Prozent (0–100)

Matching-Prozess (STRIKT befolgen):
1. LIES den "→ Parsed:" Kontext für jede Schicht!
2. SCHICHTCODE-PRÜFUNG → D="Deck", B="Binder", T="Trag" im EPD-Namen?
3. PRÜFE EPD gegen Ausschluss-Liste
4. SUCHE in EPD-Feldern nach TYP-Begriffen
5. BERECHNE Confidence STRIKT nach Schicht-Matching!

Confidence-Kalibrierung (⚠️ STRIKT!):
- 85–100: KORREKTER SCHICHT-Begriff + TYP + Details
- 60–84: KORREKTER SCHICHT-Begriff + TYP
- 40–49: TYP vorhanden, aber FALSCHER/KEIN Schicht-Begriff
- <30: Ausschluss-Begriff (NICHT LISTEN!)

Ausschluss-Begriffe: {PromptBuilder._get_ausschluss_liste_kompakt()}"""
        else:
            criteria = f"""{glossary}

Bewertungskriterien:
- Verwende nur die oben gelisteten EPD-Einträge
- PFLICHT: Nutze das Glossar für EXAKTE Interpretation!
- ⚠️ SCHICHTCODE-MATCHING IST PFLICHT!
- Gib eine kurze Begründung
- Liefere Confidence-Score in Prozent (0–100)

Matching-Prozess (STRIKT):
1. LIES den "→ Parsed:" Kontext für jede Schicht!
2. SCHICHTCODE-PRÜFUNG → D="Deck", B="Binder", T="Trag" im EPD-Namen?
3. PRÜFE EPD-Name gegen Ausschluss-Liste
4. VERGLEICHE mit TYP-Begriffen
5. BERECHNE Confidence STRIKT!

Confidence-Kalibrierung (⚠️ STRIKT!):
- 85–100: KORREKTER SCHICHT-Begriff + TYP
- 60–84: KORREKTER SCHICHT-Begriff + TYP
- 40–49: TYP vorhanden, aber FALSCHER/KEIN Schicht-Begriff
- <30: Ausschluss-Begriff (NICHT LISTEN!)

Ausschluss-Begriffe: {PromptBuilder._get_ausschluss_liste_kompakt()}"""

        return f"""
{'='*70}
AUFGABE
{'='*70}

Finde die {max_results} BESTEN EPD-Matches für JEDE der folgenden Schichten.
⚠️ BEACHTE den "→ Parsed:" Kontext - dort steht welcher Schicht-Begriff im EPD-Namen sein MUSS!

{material_list}

{criteria}

Antwort-Format (NUR JSON, ohne Fließtext):
{{
  "results": [
    {{
      "schicht": 1,
      "matches": [
        {{
          "id": ZAHL,
          "begruendung": "Begründung: [SCHICHT-Prüfung] + [TYP] + Details",
          "confidence": 0-100
        }}
      ]
    }},
    {{
      "schicht": 2,
      "matches": [...]
    }}
  ]
}}

KRITISCH:
- Verwende die EXAKTE ID (Zahl) aus der EPD-Liste
- LIES den "→ Parsed:" Kontext für jede Schicht!
- ⚠️ SCHICHTCODE PRÜFEN: D→"Deck", B→"Binder", T→"Trag" im EPD-Namen!
- EPDs mit falschem Schichttyp: Confidence < 50!
- EPDs mit Ausschluss-Begriffen: Confidence < 30!
- Sortiere nach Relevanz (beste zuerst)
- Maximal {max_results} Matches pro Schicht
- Liefere Ergebnisse für ALLE {len(materials)} Schichten
"""

    @staticmethod
    def _build_task_section(material_name: str, context: Optional[Dict[str, Any]], max_results: int) -> str:
        """Erstellt Aufgabenstellung für Einzelmaterial."""
        schicht_name = context.get("NAME", "") if context else ""
        glossary = PromptBuilder._get_material_glossary()

        # Parse mit Fallback!
        parsed = parse_material_input(material_name, schicht_name)

        parsed_hint = ""
        if parsed.get("schicht") and parsed.get("schicht_epd_muss_enthalten"):
            schicht_muss = parsed.get("schicht_epd_muss_enthalten", "")
            parsed_hint = f"""
⚠️ WICHTIG für dieses Material:
   Schichtcode: {parsed['schicht']} = {parsed.get('schicht_name', '')}
   → EPD-Name MUSS "{schicht_muss}" enthalten für Confidence >= 60%!
"""

        if MatchingConfig.USE_DETAIL_MATCHING:
            context_hint = f"\nZusatz-Kontext: Schichtname \"{schicht_name}\"" if schicht_name else ""

            criteria = f"""{glossary}
{context_hint}
{parsed_hint}

Bewertungskriterien:
- Verwende nur die oben gelisteten EPD-Einträge
- PFLICHT: Nutze das Glossar!
- ⚠️ SCHICHTCODE-MATCHING IST PFLICHT!
- Nutze ALLE EPD-Felder
- Gib Begründung mit Zitaten
- Confidence-Score 0–100

Confidence-Kalibrierung (⚠️ STRIKT!):
- 85–100: KORREKTER SCHICHT-Begriff + TYP + Details
- 60–84: KORREKTER SCHICHT-Begriff + TYP
- 40–49: TYP vorhanden, aber FALSCHER/KEIN Schicht-Begriff
- <30: Ausschluss-Begriff (NICHT LISTEN!)

Ausschluss-Begriffe: {PromptBuilder._get_ausschluss_liste_kompakt()}"""
        else:
            context_hint = f"\nZusatz-Kontext: Schichtname \"{schicht_name}\"" if schicht_name else ""

            criteria = f"""{glossary}
{context_hint}
{parsed_hint}

Bewertungskriterien:
- Verwende nur die oben gelisteten EPD-Einträge
- PFLICHT: Nutze das Glossar!
- ⚠️ SCHICHTCODE-MATCHING IST PFLICHT!
- Gib Begründung
- Confidence-Score 0–100

Confidence-Kalibrierung (⚠️ STRIKT!):
- 85–100: KORREKTER SCHICHT-Begriff + TYP
- 60–84: KORREKTER SCHICHT-Begriff + TYP
- 40–49: TYP vorhanden, aber FALSCHER/KEIN Schicht-Begriff
- <30: Ausschluss-Begriff (NICHT LISTEN!)

Ausschluss-Begriffe: {PromptBuilder._get_ausschluss_liste_kompakt()}"""

        return f"""
{'='*70}
AUFGABE
{'='*70}

Finde die {max_results} BESTEN EPD-Matches für das Material "{material_name}".
{parsed_hint}

{criteria}

Antwort-Format (NUR JSON, ohne Fließtext):
{{
  "matches": [
    {{
      "id": ZAHL,
      "begruendung": "Begründung: [SCHICHT-Prüfung] + [TYP] + Details",
      "confidence": 0-100
    }}
  ]
}}

KRITISCH:
- Verwende die EXAKTE ID (Zahl) aus der Liste
- ⚠️ SCHICHTCODE PRÜFEN!
- EPDs mit falschem Schichttyp: Confidence < 50!
- Sortiere nach Relevanz
- Maximal {max_results} Einträge
"""