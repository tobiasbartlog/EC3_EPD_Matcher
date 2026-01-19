"""Prompt-Generierung für EPD-Matching - FIXED VERSION.

FIX: GPT liefert jetzt IMMER die angeforderte Anzahl Matches.
"""
from typing import Dict, Any, List, Optional

from config.settings import MatchingConfig

# Import des Asphalt-Glossars
try:
    from utils.asphalt_glossar import (
        generate_prompt_glossary,
        generate_material_context,
        parse_material_input,
        filter_epds_for_material,
        AUSSCHLUSS_BEGRIFFE
    )
except ImportError:
    # Fallback wenn Glossar nicht verfügbar
    AUSSCHLUSS_BEGRIFFE = ["Betonpflaster", "Pflasterstein", "Zement", "Mörtel"]
    def parse_material_input(m, s): return {"ist_asphalt": False}
    def generate_material_context(m, s): return f"Material: {m}"
    def generate_prompt_glossary(): return ""


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
        """Erstellt Header für Batch-Matching."""
        header = f"EPD-Matching für {len(materials)} Bauschichten\n\n"

        for i, mat in enumerate(materials, 1):
            material_name = mat.get("material_name", "Unbekannt")
            context = mat.get("context", {})
            schicht_name = context.get("NAME", "")

            if schicht_name:
                header += f"SCHICHT {i}: {schicht_name}\n"
                header += f"  Material: {material_name}\n"
            else:
                header += f"SCHICHT {i}: \"{material_name}\"\n"

            # Parsed Material-Kontext
            parsed_context = generate_material_context(material_name, schicht_name)
            header += f"  → {parsed_context}\n\n"

        return header

    @staticmethod
    def _build_header(material_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Erstellt Prompt-Header für Einzelmaterial."""
        schicht_name = context.get("NAME", "") if context else ""

        header = "EPD-Matching\n\n"

        if schicht_name:
            header += f"Schicht: {schicht_name}\n"

        header += f'Material: "{material_name}"\n'

        parsed_context = generate_material_context(material_name, schicht_name)
        header += f"→ {parsed_context}\n"

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

        return "\nKontext:\n" + "\n".join(lines)

    @staticmethod
    def _build_epd_list(epds: List[Dict[str, Any]]) -> str:
        """Erstellt formatierte EPD-Liste."""
        header = f"\n{'='*60}\nVERFÜGBARE EPDs ({len(epds)})\n{'='*60}"

        if MatchingConfig.USE_DETAIL_MATCHING:
            # Detail-Modus
            entries = []
            for i, epd in enumerate(epds, 1):
                epd_id = epd.get("id")
                name = str(epd.get("name", "N/A"))[:200]
                klassifizierung = str(epd.get("klassifizierung", ""))[:100]

                entry_lines = [f"\n{i}. ID: {epd_id}", f"   Name: {name}"]

                if klassifizierung:
                    entry_lines.append(f"   Klassifizierung: {klassifizierung}")

                tech_desc = str(epd.get("technischeBeschreibung", ""))[:200]
                if tech_desc:
                    entry_lines.append(f"   Beschreibung: {tech_desc}...")

                entries.append("\n".join(entry_lines))
        else:
            # Kompakt-Modus
            entries = []
            for i, epd in enumerate(epds, 1):
                epd_id = epd.get("id")
                name = str(epd.get("name", "N/A"))
                entries.append(f"{i}. ID: {epd_id} | {name}")

        return header + "\n" + "\n".join(entries)

    @staticmethod
    def _build_batch_task_section(materials: List[Dict[str, Any]], max_results: int) -> str:
        """
        Erstellt Aufgabenstellung für Batch-Matching.

        FIX: Explizite Anweisung für GENAU max_results Matches pro Schicht.
        """
        # Material-Liste erstellen
        material_lines = []
        for i, mat in enumerate(materials, 1):
            mat_name = mat.get('material_name', 'Unbekannt')
            context = mat.get('context', {})
            context_name = context.get('NAME', 'Unbekannt')

            parsed = parse_material_input(mat_name, context_name)

            line = f"  {i}. \"{mat_name}\" (Schicht: {context_name})"

            if parsed.get("schicht_epd_muss_enthalten"):
                line += f" → bevorzuge EPDs mit \"{parsed['schicht_epd_muss_enthalten']}\""

            material_lines.append(line)

        material_list = "\n".join(material_lines)
        ausschluss = ", ".join(AUSSCHLUSS_BEGRIFFE[:8])

        return f"""
{'='*60}
AUFGABE
{'='*60}

Finde die {max_results} besten EPD-Matches für JEDE der {len(materials)} Schichten.

Materialien:
{material_list}

WICHTIGE REGELN:
1. Liefere bis zu {max_results} Matches pro Schicht - Stoppe wenn keine sinnvollen Matches mehr vorhanden sind!
2. Verwende nur IDs aus der obigen EPD-Liste
3. Sortiere nach Relevanz (beste zuerst)

Confidence-Bewertung:
- 85-100: Sehr guter Match (Name/Typ stimmt gut überein)
- 60-84:  Guter Match (thematisch passend)
- 40-59:  Akzeptabler Match (entfernt verwandt)
- 20-39:  Schwacher Match (nur wenn nötig um {max_results} zu erreichen)

Ausschluss-Begriffe (Confidence < 20): {ausschluss}

Antwort NUR als JSON:
{{
  "results": [
    {{
      "schicht": 1,
      "matches": [
        {{"id": 123, "begruendung": "Kurze Begründung", "confidence": 85}},
        {{"id": 456, "begruendung": "...", "confidence": 70}},
        ... (insgesamt {max_results} Einträge)
      ]
    }},
    {{
      "schicht": 2,
      "matches": [... {max_results} Einträge ...]
    }},
    ... (für alle {len(materials)} Schichten)
  ]
}}

⚠️ KRITISCH: 
- GENAU {max_results} Matches pro Schicht!
- Nur numerische IDs aus der EPD-Liste verwenden!
- Ergebnisse für ALLE {len(materials)} Schichten liefern!
"""

    @staticmethod
    def _build_task_section(material_name: str, context: Optional[Dict[str, Any]], max_results: int) -> str:
        """Erstellt Aufgabenstellung für Einzelmaterial."""
        schicht_name = context.get("NAME", "") if context else ""
        parsed = parse_material_input(material_name, schicht_name)
        ausschluss = ", ".join(AUSSCHLUSS_BEGRIFFE[:8])

        hint = ""
        if parsed.get("schicht_epd_muss_enthalten"):
            hint = f"\nHinweis: Bevorzuge EPDs mit \"{parsed['schicht_epd_muss_enthalten']}\" im Namen.\n"

        return f"""
{'='*60}
AUFGABE
{'='*60}

Finde die {max_results} besten EPD-Matches für: "{material_name}"
{hint}
WICHTIGE REGELN:
1. Liefere EXAKT {max_results} Matches - KEINE AUSNAHMEN!
2. Auch Matches mit Confidence 30-50 sind OK
3. Verwende nur IDs aus der EPD-Liste
4. Sortiere nach Relevanz

Confidence: 85-100=sehr gut, 60-84=gut, 40-59=akzeptabel, 20-39=schwach
Ausschluss (Confidence < 20): {ausschluss}

Antwort NUR als JSON:
{{
  "matches": [
    {{"id": 123, "begruendung": "Begründung", "confidence": 85}},
    ... ({max_results} Einträge!)
  ]
}}
"""

    # Legacy-Methoden für Kompatibilität
    @staticmethod
    def _get_material_glossary() -> str:
        """Gibt das Asphalt-Glossar für den Prompt zurück."""
        return generate_prompt_glossary()

    @staticmethod
    def _get_ausschluss_liste_kompakt() -> str:
        """Gibt kompakte Ausschluss-Liste zurück."""
        return ", ".join(AUSSCHLUSS_BEGRIFFE[:15])