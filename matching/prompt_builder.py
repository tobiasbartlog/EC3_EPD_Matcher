"""Prompt-Generierung für EPD-Matching."""
from typing import Dict, Any, List, Optional

from config.settings import MatchingConfig


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
        Erstellt Prompt für EINZELNES Material (Legacy, falls Batch nicht genutzt).

        Args:
            material_name: Name des zu matchenden Materials
            epds: Liste verfügbarer EPD-Einträge
            context: Zusätzlicher Kontext (NAME, Volumen, GUID)
            max_results: Maximale Anzahl Ergebnisse

        Returns:
            Formatierter Prompt-String
        """
        sections = [
            PromptBuilder._build_header(material_name),
            PromptBuilder._build_context_section(context),
            PromptBuilder._build_epd_list(epds),
            PromptBuilder._build_task_section(material_name, max_results)
        ]

        return "\n".join(s for s in sections if s)

    @staticmethod
    def _build_batch_header(materials: List[Dict[str, Any]]) -> str:
        """Erstellt Header für Batch-Matching."""
        header = f"Baumaterial-Matching (Batch: {len(materials)} Schichten)\n\n"

        for i, mat in enumerate(materials, 1):
            material_name = mat.get("material_name", "Unbekannt")
            context = mat.get("context", {})

            header += f"SCHICHT {i}: \"{material_name}\"\n"

            if context:
                if context.get("NAME"):
                    header += f"  - Name: {context['NAME']}\n"
                if context.get("Volumen"):
                    header += f"  - Volumen: {context['Volumen']} m³\n"
                if context.get("GUID"):
                    header += f"  - IFC GUIDs: {len(context['GUID'])} Elemente\n"

            header += "\n"

        return header

    @staticmethod
    def _build_header(material_name: str) -> str:
        """Erstellt Prompt-Header für Einzelmaterial."""
        return f'Baumaterial-Matching\n\nZu matchen: "{material_name}"'

    @staticmethod
    def _build_context_section(context: Optional[Dict[str, Any]]) -> str:
        """Erstellt Kontext-Sektion wenn vorhanden."""
        if not context:
            return ""

        lines = []
        if context.get("NAME"):
            lines.append(f"- Schicht: {context['NAME']}")
        if context.get("Volumen"):
            lines.append(f"- Volumen: {context['Volumen']} m³")
        if context.get("GUID"):
            lines.append(f"- IFC GUIDs: {len(context['GUID'])} Elemente")

        if not lines:
            return ""

        return "\nKontext:\n" + "\n".join(lines)

    @staticmethod
    def _build_epd_list(epds: List[Dict[str, Any]]) -> str:
        """
        Erstellt formatierte EPD-Liste.
        Modus hängt von MatchingConfig.USE_DETAIL_MATCHING ab.
        """
        header = f"\n{'='*70}\nVERFÜGBARE EPD-EINTRÄGE ({len(epds)})\n{'='*70}"

        if MatchingConfig.USE_DETAIL_MATCHING:
            # Detail-Modus: Name + Klassifizierung + Beschreibungen
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

                anwendung = str(epd.get("anwendungsgebiet", ""))[:200]
                if anwendung:
                    entry_lines.append(f"   Anwendungsgebiet: {anwendung}...")

                entries.append("\n".join(entry_lines))
        else:
            # Namen-Modus: Nur ID + Name (kompakt)
            entries = []
            for i, epd in enumerate(epds, 1):
                epd_id = epd.get("id")
                name = str(epd.get("name", "N/A"))
                entries.append(f"{i}. ID: {epd_id} | Name: {name}")

        return header + "\n" + "\n".join(entries)

    @staticmethod
    def _build_batch_task_section(materials: List[Dict[str, Any]], max_results: int) -> str:
        """Erstellt Aufgabenstellung für Batch-Matching."""
        material_list = "\n".join([
            f"  - SCHICHT {i}: \"{mat.get('material_name', 'Unbekannt')}\""
            for i, mat in enumerate(materials, 1)
        ])

        if MatchingConfig.USE_DETAIL_MATCHING:
            criteria = """Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- Nutze ALLE verfügbaren Felder (Name, Klassifizierung, technische Beschreibung, Anmerkungen, Anwendungsgebiet)
- Gib eine kurze Begründung mit konkreten Zitaten aus den Feldern
- Liefere einen Confidence-Score in Prozent (0–100)

Confidence-Kalibrierung:
- 85–100: exakte Nennung + passende Spezifikation in technischer Beschreibung
- 60–84: starke semantische Nähe, passende Klassifizierung
- 30–59: allgemeiner Bezug ohne passende Typologie
- <30: nicht listen"""
        else:
            criteria = """Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- Matche basierend auf dem Namen
- Gib eine kurze Begründung mit Bezug zum Namen
- Liefere einen Confidence-Score in Prozent (0–100)

Confidence-Kalibrierung:
- 85–100: Name enthält exakte Materialbezeichnung (z.B. "AC 11 D S" in Name)
- 60–84: Name enthält Hauptkomponente (z.B. "Asphalt" für "AC 11 D S")
- 30–59: Name hat thematischen Bezug (z.B. "Straßenbau")
- <30: nicht listen"""

        return f"""
{'='*70}
AUFGABE
{'='*70}

Finde die {max_results} BESTEN EPD-Matches für JEDE der folgenden Schichten:

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
          "begruendung": "kurze Begründung",
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
- Sortiere Matches nach Relevanz (beste zuerst)
- Maximal {max_results} Matches pro Schicht
- Liefere Ergebnisse für ALLE {len(materials)} Schichten
"""

    @staticmethod
    def _build_task_section(material_name: str, max_results: int) -> str:
        """Erstellt Aufgabenstellung für Einzelmaterial."""
        if MatchingConfig.USE_DETAIL_MATCHING:
            criteria = """Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- Nutze ALLE verfügbaren Felder (Name, Klassifizierung, technische Beschreibung, Anmerkungen, Anwendungsgebiet)
- Gib eine kurze Begründung mit konkreten Zitaten aus den Feldern
- Liefere einen Confidence-Score in Prozent (0–100)

Confidence-Kalibrierung:
- 85–100: exakte Nennung + passende Spezifikation in technischer Beschreibung
- 60–84: starke semantische Nähe, passende Klassifizierung
- 30–59: allgemeiner Bezug ohne passende Typologie
- <30: nicht listen"""
        else:
            criteria = """Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- Matche basierend auf dem Namen
- Gib eine kurze Begründung mit Bezug zum Namen
- Liefere einen Confidence-Score in Prozent (0–100)

Confidence-Kalibrierung:
- 85–100: Name enthält exakte Materialbezeichnung (z.B. "AC 11 D S" in Name)
- 60–84: Name enthält Hauptkomponente (z.B. "Asphalt" für "AC 11 D S")
- 30–59: Name hat thematischen Bezug (z.B. "Straßenbau")
- <30: nicht listen"""

        return f"""
{'='*70}
AUFGABE
{'='*70}

Finde die {max_results} BESTEN EPD-Matches für das Material "{material_name}".

{criteria}

Antwort-Format (NUR JSON, ohne Fließtext):
{{
  "matches": [
    {{
      "id": ZAHL,
      "begruendung": "kurze Begründung",
      "confidence": 0-100
    }}
  ]
}}

KRITISCH:
- Verwende die EXAKTE ID (Zahl) aus der Liste
- Sortiere nach Relevanz (beste zuerst)
- Maximal {max_results} Einträge
"""
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
        Erstellt Prompt für EINZELNES Material (Legacy, falls Batch nicht genutzt).

        Args:
            material_name: Name des zu matchenden Materials
            epds: Liste verfügbarer EPD-Einträge
            context: Zusätzlicher Kontext (NAME, Volumen, GUID)
            max_results: Maximale Anzahl Ergebnisse

        Returns:
            Formatierter Prompt-String
        """
        sections = [
            PromptBuilder._build_header(material_name),
            PromptBuilder._build_context_section(context),
            PromptBuilder._build_epd_list(epds),
            PromptBuilder._build_task_section(material_name, max_results)
        ]

        return "\n".join(s for s in sections if s)

    @staticmethod
    def _build_batch_header(materials: List[Dict[str, Any]]) -> str:
        """Erstellt Header für Batch-Matching."""
        header = f"Baumaterial-Matching (Batch: {len(materials)} Schichten)\n\n"

        for i, mat in enumerate(materials, 1):
            material_name = mat.get("material_name", "Unbekannt")
            context = mat.get("context", {})

            header += f"SCHICHT {i}: \"{material_name}\"\n"

            if context:
                if context.get("NAME"):
                    header += f"  - Name: {context['NAME']}\n"
                if context.get("Volumen"):
                    header += f"  - Volumen: {context['Volumen']} m³\n"
                if context.get("GUID"):
                    header += f"  - IFC GUIDs: {len(context['GUID'])} Elemente\n"

            header += "\n"

        return header

    @staticmethod
    def _build_header(material_name: str) -> str:
        """Erstellt Prompt-Header für Einzelmaterial."""
        return f'Baumaterial-Matching\n\nZu matchen: "{material_name}"'

    @staticmethod
    def _build_context_section(context: Optional[Dict[str, Any]]) -> str:
        """Erstellt Kontext-Sektion wenn vorhanden."""
        if not context:
            return ""

        lines = []
        if context.get("NAME"):
            lines.append(f"- Schicht: {context['NAME']}")
        if context.get("Volumen"):
            lines.append(f"- Volumen: {context['Volumen']} m³")
        if context.get("GUID"):
            lines.append(f"- IFC GUIDs: {len(context['GUID'])} Elemente")

        if not lines:
            return ""

        return "\nKontext:\n" + "\n".join(lines)

    @staticmethod
    def _build_epd_list(epds: List[Dict[str, Any]]) -> str:
        """Erstellt formatierte EPD-Liste mit allen verfügbaren Detail-Feldern."""
        header = f"\n{'='*70}\nVERF�ÜGBARE EPD-EINTRÄGE ({len(epds)})\n{'='*70}"

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

            # Detail-Felder hinzufügen (wenn vorhanden)
            tech_desc = str(epd.get("technischeBeschreibung", ""))[:300]
            if tech_desc:
                entry_lines.append(f"   Technische Beschreibung: {tech_desc}...")

            anmerkungen = str(epd.get("anmerkungen", ""))[:250]
            if anmerkungen:
                entry_lines.append(f"   Anmerkungen: {anmerkungen}...")

            anwendung = str(epd.get("anwendungsgebiet", ""))[:200]
            if anwendung:
                entry_lines.append(f"   Anwendungsgebiet: {anwendung}...")

            entries.append("\n".join(entry_lines))

        return header + "\n" + "\n".join(entries)

    @staticmethod
    def _build_batch_task_section(materials: List[Dict[str, Any]], max_results: int) -> str:
        """Erstellt Aufgabenstellung für Batch-Matching."""
        material_list = "\n".join([
            f"  - SCHICHT {i}: \"{mat.get('material_name', 'Unbekannt')}\""
            for i, mat in enumerate(materials, 1)
        ])

        return f"""
{'='*70}
AUFGABE
{'='*70}

Finde die {max_results} BESTEN EPD-Matches für JEDE der folgenden Schichten:

{material_list}

Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- Matche basierend auf dem Namen
- Gib eine kurze Begründung mit Bezug zum Namen
- Liefere einen Confidence-Score in Prozent (0–100)

Confidence-Kalibrierung:
- 85–100: Name enthält exakte Materialbezeichnung (z.B. "AC 11 D S" in Name)
- 60–84: Name enthält Hauptkomponente (z.B. "Asphalt" für "AC 11 D S")
- 30–59: Name hat thematischen Bezug (z.B. "Straßenbau")
- <30: nicht listen

Antwort-Format (NUR JSON, ohne Fließtext):
{{
  "results": [
    {{
      "schicht": 1,
      "matches": [
        {{
          "id": ZAHL,
          "begruendung": "kurze Begründung mit Zitaten",
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
- Sortiere Matches nach Relevanz (beste zuerst)
- Maximal {max_results} Matches pro Schicht
- Liefere Ergebnisse für ALLE {len(materials)} Schichten
"""

    @staticmethod
    def _build_task_section(material_name: str, max_results: int) -> str:
        """Erstellt Aufgabenstellung für Einzelmaterial."""
        return f"""
{'='*70}
AUFGABE
{'='*70}

Finde die {max_results} BESTEN EPD-Matches für das Material "{material_name}".

Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- Nutze ALLE verfügbaren Felder (Name, Klassifizierung, technische Beschreibung, Anmerkungen, Anwendungsgebiet)
- Gib eine kurze Begründung mit konkreten Zitaten aus den Feldern
- Liefere einen Confidence-Score in Prozent (0–100)

Confidence-Kalibrierung:
- 85–100: exakte Nennung + passende Spezifikation in technischer Beschreibung
- 60–84: starke semantische Nähe, passende Klassifizierung
- 30–59: allgemeiner Bezug ohne passende Typologie
- <30: nicht listen

Antwort-Format (NUR JSON, ohne Fließtext):
{{
  "matches": [
    {{
      "id": ZAHL,
      "begruendung": "kurze Begründung mit Zitaten",
      "confidence": 0-100
    }}
  ]
}}

KRITISCH:
- Verwende die EXAKTE ID (Zahl) aus der Liste
- Sortiere nach Relevanz (beste zuerst)
- Maximal {max_results} Einträge
"""