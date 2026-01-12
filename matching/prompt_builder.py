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
            PromptBuilder._build_header(material_name, context),
            PromptBuilder._build_context_section(context),
            PromptBuilder._build_epd_list(epds),
            PromptBuilder._build_task_section(material_name, context, max_results)
        ]

        return "\n".join(s for s in sections if s)

    @staticmethod
    def _build_batch_header(materials: List[Dict[str, Any]]) -> str:
        """Erstellt Header für Batch-Matching."""
        header = f"Baumaterial-Matching (Batch: {len(materials)} Schichten)\n\n"

        for i, mat in enumerate(materials, 1):
            material_name = mat.get("material_name", "Unbekannt")
            context = mat.get("context", {})
            schicht_name = context.get("NAME", "")

            # WICHTIG: Schichtname VOR Material nennen!
            if schicht_name:
                header += f"SCHICHT {i}: {schicht_name}\n"
                header += f"  Material: {material_name}\n"
            else:
                header += f"SCHICHT {i}: \"{material_name}\"\n"

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

        if schicht_name:
            return f'Baumaterial-Matching\n\nSchicht: {schicht_name}\nMaterial: "{material_name}"'
        else:
            return f'Baumaterial-Matching\n\nZu matchen: "{material_name}"'

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
    def _get_material_glossary() -> str:
        """Gibt detaillierte Asphalt-Lookup-Tabelle zurück (basierend auf BAM-Norm)."""
        return """
╔════════════════════════════════════════════════════════════════════╗
║  ASPHALT-BEZEICHNUNGEN NACH BAM (Bundesverband der Asphaltindustrie)  ║
╚════════════════════════════════════════════════════════════════════╝

📋 AUFBAU EINER ASPHALT-BEZEICHNUNG:
   [TYP] [GRÖSSTKOR] [SCHICHT] [EIGENSCHAFTEN]
   
   Beispiel: AC 16 B S
   ├─ AC = Asphaltbeton (Typ)
   ├─ 16 = Größtkorn 16 mm
   ├─ B = Binderschicht
   └─ S = Splittmastixcharakter

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  ASPHALT-TYPEN (TYP-CODE)

┌─────────┬──────────────────────────┬─────────────────────────────────┐
│  CODE   │  VOLLSTÄNDIGER NAME      │  EPD-SUCHBEGRIFFE               │
├─────────┼──────────────────────────┼─────────────────────────────────┤
│  AC     │  Asphaltbeton            │  Asphaltbeton, Asphalt,         │
│         │                          │  Asphalttragschicht,            │
│         │                          │  Asphaltbinder, Bitumen         │
├─────────┼──────────────────────────┼─────────────────────────────────┤
│  SMA    │  Splittmastixasphalt     │  Splittmastixasphalt,           │
│         │                          │  Splittmastix, SMA              │
├─────────┼──────────────────────────┼─────────────────────────────────┤
│  PA     │  Offenporiger Asphalt    │  Drainasphalt, offenporig,      │
│         │  (Dränasphalt)           │  wasserdurchlässig, Dränasphalt │
├─────────┼──────────────────────────┼─────────────────────────────────┤
│  MA     │  Asphaltmastix           │  Gussasphalt, Asphaltmastix,    │
│         │  (Gussasphalt)           │  Mastix, Guss                   │
└─────────┴──────────────────────────┴─────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2️⃣  SCHICHTCODES (POSITION IN DER STRASSE) - ⚠️ KRITISCH FÜR MATCHING!

┌──────┬─────────────────┬────────────────────────────────────────────┐
│ CODE │  SCHICHTTYP     │  EPD-NAME MUSS ENTHALTEN (für Conf. ≥60)   │
├──────┼─────────────────┼────────────────────────────────────────────┤
│  D   │  Deckschicht    │  "Deck" (z.B. Asphaltdeckschicht,          │
│      │  (oberste)      │  Deckschicht, Tragdeckschicht)             │
│      │                 │  ⚠️ "Binder" oder "Trag" allein = <50%!    │
├──────┼─────────────────┼────────────────────────────────────────────┤
│  B   │  Binderschicht  │  "Binder" (z.B. Asphaltbinder,             │
│      │  (mittlere)     │  Binderschicht, Asphaltbinderschicht)      │
│      │                 │  ⚠️ "Deck" oder "Trag" allein = <50%!      │
├──────┼─────────────────┼────────────────────────────────────────────┤
│  T   │  Tragschicht    │  "Trag" (z.B. Asphalttragschicht,          │
│      │  (unterste)     │  Tragschicht, Tragdeckschicht)             │
│      │                 │  ⚠️ "Deck" oder "Binder" allein = <50%!    │
└──────┴─────────────────┴────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3️⃣  GRÖSSTKORN (ZAHL IN MM)

Häufige Werte: 5, 8, 11, 16, 22, 32
→ Für EPD-Matching meist SEKUNDÄR relevant
→ Fokus auf Typ + Schichtcode!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4️⃣  EIGENSCHAFTEN-CODES

┌──────┬─────────────────────────────────────────────────────────────┐
│ CODE │  BEDEUTUNG                                                  │
├──────┼─────────────────────────────────────────────────────────────┤
│  S   │  Splittmastixcharakter (hoher Splittanteil)                │
│  SG  │  mit Gesteinsmehl-Zusatz                                    │
│  N   │  niedrig dosiertes Bindemittel                             │
│  H   │  hochdosiertes Bindemittel                                 │
└──────┴─────────────────────────────────────────────────────────────┘

→ Für EPD-Matching meist SEKUNDÄR relevant

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5️⃣  BINDEMITTEL-HINWEISE

┌─────────────────────────┬─────────────────────────────────────────┐
│  BEGRIFF IN BEZEICHNUNG │  EPD-SUCHBEGRIFFE                       │
├─────────────────────────┼─────────────────────────────────────────┤
│  Polymermodifiziert     │  polymer, modifiziert, Elastomer,       │
│  PmB                    │  PmB, Polymer-Bitumen                   │
│  10/40-65A, 25/55-55    │  Bitumen, Bindemittel                   │
└─────────────────────────┴─────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📖 MATCHING-BEISPIELE MIT SCHICHT-PRÜFUNG:

Beispiel 1: "AC 11 D S" (Deckschicht)
├─ AC → Asphaltbeton ✓
├─ D  → Deckschicht → EPD-Name MUSS "Deck" enthalten!
├─ ✅ "Asphaltdeckschicht" → Confidence 85-100%
├─ ✅ "Tragdeckschicht" → Confidence 60-84% (hat "Deck")
├─ ❌ "Asphaltbinder" → Confidence <50% (FALSCHER Schichttyp!)
└─ ❌ "Asphalttragschicht" → Confidence <50% (FALSCHER Schichttyp!)

Beispiel 2: "AC 16 B S SG mit Polymermodifiziertem Bindemittel"
├─ AC → Asphaltbeton ✓
├─ B  → Binderschicht → EPD-Name MUSS "Binder" enthalten!
├─ ✅ "Asphaltbinder" → Confidence 85-100%
├─ ✅ "Asphaltbinderschicht" → Confidence 85-100%
├─ ❌ "Asphaltdeckschicht" → Confidence <50% (FALSCHER Schichttyp!)
└─ ❌ "Asphalttragschicht" → Confidence <50% (FALSCHER Schichttyp!)

Beispiel 3: "AC 22 T S" (Tragschicht)
├─ AC → Asphaltbeton ✓
├─ T  → Tragschicht → EPD-Name MUSS "Trag" enthalten!
├─ ✅ "Asphalttragschicht" → Confidence 85-100%
├─ ✅ "Tragdeckschicht" → Confidence 60-84% (hat "Trag")
├─ ❌ "Asphaltbinder" → Confidence <50% (FALSCHER Schichttyp!)
└─ ❌ "Asphaltdeckschicht" → Confidence <50% (FALSCHER Schichttyp!)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ AUSSCHLUSS-LISTE (NIEMALS FÜR ASPHALT MATCHEN):

Diese Materialien sind KEIN Asphalt und dürfen bei AC/SMA/PA/MA NIEMALS 
als Match vorgeschlagen werden:

🚫 Betonprodukte:
   - Betonpflaster, Betonstein, Pflasterstein
   - Normaler Beton (C20/25, C30/37, C35/45, etc.)
   - Betondecke, Betonschicht
   - Transportbeton, Fertigbeton

🚫 Bindemittel (solo, ohne Asphalt-Kontext):
   - Zement (solo), Portland-Zement
   - Mörtel, Estrich
   - Kalk, Kalkmörtel

🚫 Andere Baustoffe:
   - Kalksandstein, Mauerwerk, Ziegel
   - Anhydrit, Gips
   - Holz, Holzwerkstoffe
   - Stahl, Aluminium, Metalle
   - Kunststoffe, Dämmstoffe

⚠️  REGEL: Wenn EPD-Name einen dieser Begriffe enthält → Confidence < 30!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 MATCHING-PROZESS (SCHRITT FÜR SCHRITT):

Schritt 1: PARSE die Material-Bezeichnung
   → Identifiziere: TYP (AC/SMA/PA/MA), SCHICHTCODE (D/B/T), BINDEMITTEL

Schritt 2: SCHICHTCODE-PRÜFUNG (⚠️ KRITISCH!)
   → D = EPD-Name muss "Deck" enthalten
   → B = EPD-Name muss "Binder" enthalten  
   → T = EPD-Name muss "Trag" enthalten
   → OHNE korrekten Schicht-Begriff im EPD-Namen: Confidence < 50!

Schritt 3: PRÜFE EPD-Namen gegen AUSSCHLUSS-LISTE
   → Enthält EPD Ausschluss-Begriff? → VERWERFEN (Confidence < 30)

Schritt 4: SUCHE EPD-Namen nach TYP-Begriffen
   → EPD-Name enthält "Asphalt", "Bitumen" etc.? → Kandidat

Schritt 5: BERECHNE Confidence (STRIKT!)
   → Korrekter SCHICHT-Begriff + TYP + Details: 85-100%
   → Korrekter SCHICHT-Begriff + TYP: 60-84%
   → NUR TYP, aber FALSCHER/KEIN Schicht-Begriff: 40-49%
   → Nur Bitumen o.ä.: 30-39%
   → Ausschluss-Begriff: < 30%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  KRITISCHE SCHICHT-VERWECHSLUNGEN (NIEMALS MACHEN!):

❌ FALSCH: "AC 11 D S" (Deckschicht) → "Asphaltbinder" (85%)
   RICHTIG: "AC 11 D S" (Deckschicht) → "Asphaltbinder" (<50%)
   Grund: D = Deckschicht, aber "Asphaltbinder" = Binderschicht!

❌ FALSCH: "AC 11 D S" (Deckschicht) → "Asphalttragschicht" (80%)
   RICHTIG: "AC 11 D S" (Deckschicht) → "Asphalttragschicht" (<50%)
   Grund: D = Deckschicht, aber "Asphalttragschicht" = Tragschicht!

❌ FALSCH: "AC 16 B S" (Binderschicht) → "Asphaltdeckschicht" (85%)
   RICHTIG: "AC 16 B S" (Binderschicht) → "Asphaltdeckschicht" (<50%)
   Grund: B = Binderschicht, aber "Asphaltdeckschicht" = Deckschicht!

✓ RICHTIG: "AC 11 D S" → "Asphaltdeckschicht" (85-100%)
✓ RICHTIG: "AC 16 B S" → "Asphaltbinder" (85-100%)
✓ RICHTIG: "AC 22 T S" → "Asphalttragschicht" (85-100%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    @staticmethod
    def _build_batch_task_section(materials: List[Dict[str, Any]], max_results: int) -> str:
        """Erstellt Aufgabenstellung für Batch-Matching."""
        material_list = "\n".join([
            f"  - SCHICHT {i} ({mat.get('context', {}).get('NAME', 'Unbekannt')}): \"{mat.get('material_name', 'Unbekannt')}\""
            for i, mat in enumerate(materials, 1)
        ])

        glossary = PromptBuilder._get_material_glossary()

        if MatchingConfig.USE_DETAIL_MATCHING:
            criteria = f"""{glossary}

Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- PFLICHT: Nutze die Lookup-Tabellen für EXAKTE Interpretation der Bezeichnungen!
- ⚠️ SCHICHTCODE-MATCHING IST PFLICHT! EPD-Name muss korrekten Schicht-Begriff enthalten!
- Nutze ALLE verfügbaren EPD-Felder (Name, Klassifizierung, technische Beschreibung, Anmerkungen, Anwendungsgebiet)
- Gib eine kurze Begründung mit konkreten Zitaten aus den EPD-Feldern
- Liefere einen Confidence-Score in Prozent (0–100)

Matching-Prozess (befolge STRIKT):
1. PARSE Material-Bezeichnung → finde TYP-Code (AC/SMA/PA/MA) + SCHICHT-Code (D/B/T)
2. SCHICHTCODE-PRÜFUNG → D="Deck", B="Binder", T="Trag" im EPD-Namen?
3. PRÜFE EPD gegen Ausschluss-Liste → verwerfe wenn Ausschluss-Begriff enthalten
4. SUCHE in EPD-Feldern nach TYP-Begriffen aus Lookup-Tabellen
5. BERECHNE Confidence STRIKT nach Schicht-Matching!

Confidence-Kalibrierung (⚠️ STRIKT EINHALTEN!):
- 85–100: EPD-Name enthält KORREKTEN SCHICHT-Begriff (D→"Deck", B→"Binder", T→"Trag") + TYP-Begriff + Details + KEIN Ausschluss
- 60–84: EPD-Name enthält KORREKTEN SCHICHT-Begriff + TYP-Begriff + KEIN Ausschluss
- 40–49: EPD-Name enthält TYP-Begriff ABER FALSCHEN oder KEINEN Schicht-Begriff + KEIN Ausschluss
- 30–39: EPD hat schwachen Asphalt-Bezug + KEIN Ausschluss
- <30: EPD enthält Ausschluss-Begriff ODER kein Asphalt-Bezug (NICHT LISTEN!)

⚠️ SCHICHT-MATCHING BEISPIELE:
- Material "AC 11 D S" + EPD "Asphaltbinder" → Confidence <50! (D≠Binder)
- Material "AC 11 D S" + EPD "Asphaltdeckschicht" → Confidence 85+! (D=Deck ✓)
- Material "AC 16 B S" + EPD "Asphalttragschicht" → Confidence <50! (B≠Trag)
- Material "AC 16 B S" + EPD "Asphaltbinder" → Confidence 85+! (B=Binder ✓)"""
        else:
            criteria = f"""{glossary}

Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- PFLICHT: Nutze die Lookup-Tabellen für EXAKTE Interpretation der Bezeichnungen!
- ⚠️ SCHICHTCODE-MATCHING IST PFLICHT! EPD-Name muss korrekten Schicht-Begriff enthalten!
- Gib eine kurze Begründung mit Bezug zu den Lookup-Tabellen
- Liefere einen Confidence-Score in Prozent (0–100)

Matching-Prozess (befolge STRIKT):
1. PARSE Material-Bezeichnung → finde TYP-Code + SCHICHT-Code
2. SCHICHTCODE-PRÜFUNG → D="Deck", B="Binder", T="Trag" im EPD-Namen?
3. PRÜFE EPD-Name gegen Ausschluss-Liste → verwerfe wenn Ausschluss-Begriff
4. VERGLEICHE EPD-Namen mit TYP-Begriffen aus Lookup-Tabellen
5. BERECHNE Confidence STRIKT nach Schicht-Matching!

Confidence-Kalibrierung (⚠️ STRIKT EINHALTEN!):
- 85–100: EPD-Name enthält KORREKTEN SCHICHT-Begriff + TYP-Begriff + KEIN Ausschluss
- 60–84: EPD-Name enthält KORREKTEN SCHICHT-Begriff + TYP-Begriff + KEIN Ausschluss
- 40–49: EPD-Name enthält TYP-Begriff ABER FALSCHEN oder KEINEN Schicht-Begriff
- 30–39: EPD-Name hat schwachen Asphalt-Bezug
- <30: EPD-Name enthält Ausschluss-Begriff (NICHT LISTEN!)

⚠️ SCHICHT-MATCHING BEISPIELE:
- Material "AC 11 D S" + EPD "Asphaltbinder" → Confidence <50! (D≠Binder)
- Material "AC 11 D S" + EPD "Asphaltdeckschicht" → Confidence 85+! (D=Deck ✓)"""

        return f"""
{'='*70}
AUFGABE
{'='*70}

Finde die {max_results} BESTEN EPD-Matches für JEDE der folgenden Schichten.
NUTZE ZWINGEND die Lookup-Tabellen für korrektes Matching!
⚠️ PRÜFE IMMER: Passt der SCHICHTCODE im Material zum SCHICHT-Begriff im EPD-Namen?

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
          "begruendung": "Begründung: [TYP] + [SCHICHT-Prüfung: Material-Code X = EPD enthält Y] + Details",
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
- PARSE Material-Bezeichnung mit Lookup-Tabellen!
- ⚠️ SCHICHTCODE PRÜFEN: D→"Deck", B→"Binder", T→"Trag" im EPD-Namen!
- EPDs mit falschem Schichttyp haben Confidence < 50!
- EPDs mit "Betonpflaster", "Beton C20", "Zement" etc. haben Confidence < 30!
- Sortiere Matches nach Relevanz (beste zuerst)
- Maximal {max_results} Matches pro Schicht
- Liefere Ergebnisse für ALLE {len(materials)} Schichten
"""

    @staticmethod
    def _build_task_section(material_name: str, context: Optional[Dict[str, Any]], max_results: int) -> str:
        """Erstellt Aufgabenstellung für Einzelmaterial."""
        schicht_name = context.get("NAME", "") if context else ""
        glossary = PromptBuilder._get_material_glossary()

        if MatchingConfig.USE_DETAIL_MATCHING:
            if schicht_name:
                context_hint = f"""
Zusatz-Kontext: Schichtname "{schicht_name}" 
→ Nutze diesen als Bestätigung des Schichtcodes aus der Bezeichnung"""
            else:
                context_hint = ""

            criteria = f"""{glossary}
{context_hint}

Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- PFLICHT: Nutze die Lookup-Tabellen für EXAKTE Interpretation!
- ⚠️ SCHICHTCODE-MATCHING IST PFLICHT!
- Nutze ALLE EPD-Felder (Name, Klassifizierung, technische Beschreibung, Anmerkungen, Anwendungsgebiet)
- Gib eine kurze Begründung mit konkreten Zitaten
- Liefere einen Confidence-Score in Prozent (0–100)

Matching-Prozess:
1. PARSE → finde TYP + SCHICHT aus Material-Bezeichnung
2. SCHICHTCODE-PRÜFUNG → D="Deck", B="Binder", T="Trag" im EPD-Namen?
3. PRÜFE → verwerfe EPDs mit Ausschluss-Begriffen
4. SUCHE → finde TYP-Begriffe in EPD-Feldern
5. BERECHNE → Confidence STRIKT nach Schicht-Matching!

Confidence-Kalibrierung (⚠️ STRIKT!):
- 85–100: KORREKTER SCHICHT-Begriff + TYP + Details + kein Ausschluss
- 60–84: KORREKTER SCHICHT-Begriff + TYP + kein Ausschluss
- 40–49: TYP vorhanden, aber FALSCHER/KEIN Schicht-Begriff
- <30: Ausschluss-Begriff vorhanden (NICHT LISTEN!)"""
        else:
            if schicht_name:
                context_hint = f"""
Zusatz-Kontext: Schichtname "{schicht_name}" """
            else:
                context_hint = ""

            criteria = f"""{glossary}
{context_hint}

Bewertungskriterien:
- Verwende nur die oben gelisteten Einträge
- PFLICHT: Nutze die Lookup-Tabellen für EXAKTE Interpretation!
- ⚠️ SCHICHTCODE-MATCHING IST PFLICHT!
- Gib eine kurze Begründung mit Bezug zu Tabellen
- Liefere einen Confidence-Score in Prozent (0–100)

Matching-Prozess:
1. PARSE → TYP + SCHICHT aus Material-Bezeichnung
2. SCHICHTCODE-PRÜFUNG → D="Deck", B="Binder", T="Trag" im EPD-Namen?
3. PRÜFE → Ausschluss-Liste
4. VERGLEICHE → EPD-Namen mit TYP-Begriffen
5. BERECHNE → Confidence STRIKT!

Confidence-Kalibrierung (⚠️ STRIKT!):
- 85–100: Name hat KORREKTEN SCHICHT-Begriff + TYP + kein Ausschluss
- 60–84: Name hat KORREKTEN SCHICHT-Begriff + TYP
- 40–49: Name hat TYP, aber FALSCHEN/KEINEN Schicht-Begriff
- <30: Ausschluss-Begriff (NICHT LISTEN!)"""

        return f"""
{'='*70}
AUFGABE
{'='*70}

Finde die {max_results} BESTEN EPD-Matches für das Material "{material_name}".
NUTZE ZWINGEND die Lookup-Tabellen!
⚠️ PRÜFE: Passt der SCHICHTCODE zum SCHICHT-Begriff im EPD-Namen?

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
- PARSE mit Lookup-Tabellen!
- ⚠️ SCHICHTCODE PRÜFEN: D→"Deck", B→"Binder", T→"Trag"!
- EPDs mit falschem Schichttyp: Confidence < 50!
- Sortiere nach Relevanz (beste zuerst)
- Maximal {max_results} Einträge
"""