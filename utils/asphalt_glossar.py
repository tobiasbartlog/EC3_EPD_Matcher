"""
Asphalt-Glossar für EPD-Matching
================================
Basierend auf: TL Asphalt-StB 07/13 (Technische Lieferbedingungen für Asphaltmischgut
für den Bau von Verkehrsflächenbefestigungen, Ausgabe 2007/Fassung 2013)

Verwendung:
    from utils.asphalt_glossar import (
        parse_material_input,
        get_suchbegriffe_fuer_matching,
        generate_prompt_glossary,
        filter_epds_for_material,
        AUSSCHLUSS_BEGRIFFE
    )
"""

import re
from typing import Dict, List, Optional, Any, Tuple


# =============================================================================
# ASPHALTMISCHGUTARTEN (Hauptkategorien nach DIN EN 13108)
# =============================================================================

ASPHALT_TYPES: Dict[str, Dict[str, Any]] = {
    "AC": {
        "name_de": "Asphaltbeton",
        "name_en": "Asphalt Concrete",
        "norm": "DIN EN 13108-1",
        "beschreibung": "Asphaltmischgut mit abgestufter Korngrößenverteilung",
        "suchbegriffe": [
            "Asphaltbeton", "Asphalt", "Bitumen", "bituminös",
            "Asphaltmischgut", "Heißasphalt", "Walzasphalt"
        ],
        "fuzzy_matches": [
            "aspahlt", "asphalt", "bitumen", "bituminös"
        ]
    },
    "SMA": {
        "name_de": "Splittmastixasphalt",
        "name_en": "Stone Mastic Asphalt",
        "norm": "DIN EN 13108-5",
        "beschreibung": "Asphaltmischgut mit Ausfallkörnung und Zusätzen",
        "suchbegriffe": [
            "Splittmastixasphalt", "Splittmastix", "SMA",
            "Stone Mastic", "Mastixasphalt"
        ],
        "fuzzy_matches": ["splittmastix", "sma", "mastix"]
    },
    "MA": {
        "name_de": "Gussasphalt",
        "name_en": "Mastic Asphalt",
        "norm": "DIN EN 13108-6",
        "beschreibung": "Dichtes Asphaltmischgut, gießbar und streichfähig",
        "suchbegriffe": [
            "Gussasphalt", "Mastic Asphalt", "Asphaltmastix",
            "Gießasphalt", "MA"
        ],
        "fuzzy_matches": ["gussasphalt", "gießasphalt", "mastic"]
    },
    "PA": {
        "name_de": "Offenporiger Asphalt",
        "name_en": "Porous Asphalt",
        "norm": "DIN EN 13108-7",
        "beschreibung": "Asphaltmischgut mit hohem Hohlraumanteil",
        "suchbegriffe": [
            "Offenporiger Asphalt", "OPA", "Drainasphalt",
            "Porous Asphalt", "Drainageschicht", "lärmmindernd",
            "Flüsterasphalt", "PA"
        ],
        "fuzzy_matches": ["offenporig", "drainasphalt", "opa", "flüsterasphalt"]
    }
}


# =============================================================================
# SCHICHTCODES (Nationale Ergänzung Deutschland)
# =============================================================================

LAYER_CODES: Dict[str, Dict[str, Any]] = {
    "T": {
        "name_de": "Asphalttragschicht",
        "kurzform": "Tragschicht",
        "position": "unten",
        "epd_muss_enthalten": "Trag",
        "suchbegriffe": [
            "Asphalttragschicht", "Tragschicht", "Asphalt-Tragschicht",
            "bituminöse Tragschicht", "ATS"
        ],
        "name_varianten": ["tragschicht", "trag"]
    },
    "B": {
        "name_de": "Asphaltbinder",
        "kurzform": "Binderschicht",
        "position": "mitte",
        "epd_muss_enthalten": "Binder",
        "suchbegriffe": [
            "Asphaltbinder", "Binderschicht", "Asphaltbinderschicht",
            "Binder", "ABi"
        ],
        "name_varianten": ["binderschicht", "binder"]
    },
    "D": {
        "name_de": "Asphaltdeckschicht",
        "kurzform": "Deckschicht",
        "position": "oben",
        "epd_muss_enthalten": "Deck",
        "suchbegriffe": [
            "Asphaltdeckschicht", "Deckschicht", "Asphalt-Deckschicht",
            "Verschleißschicht", "Fahrbahndecke", "ADS", "Decke"
        ],
        "name_varianten": ["deckschicht", "deck", "decke", "verschleiß"]
    },
    "TD": {
        "name_de": "Asphalttragdeckschicht",
        "kurzform": "Tragdeckschicht",
        "position": "kombiniert",
        "epd_muss_enthalten": "Tragdeck",
        "suchbegriffe": [
            "Asphalttragdeckschicht", "Tragdeckschicht",
            "kombinierte Schicht", "ATDS"
        ],
        "name_varianten": ["tragdeckschicht", "tragdeck"]
    }
}


# =============================================================================
# BEANSPRUCHUNGSKLASSEN
# =============================================================================

LOAD_CLASSES: Dict[str, Dict[str, Any]] = {
    "S": {
        "name_de": "besondere Beanspruchung",
        "kurzform": "besondere",
        "anwendung": ["Autobahnen", "Bundesstraßen", "Industrieflächen"],
    },
    "N": {
        "name_de": "normale Beanspruchung",
        "kurzform": "normal",
        "anwendung": ["Landesstraßen", "Kreisstraßen"],
    },
    "L": {
        "name_de": "leichte Beanspruchung",
        "kurzform": "leicht",
        "anwendung": ["Wohnstraßen", "Radwege", "Parkplätze"],
    }
}


# =============================================================================
# VOLLSTÄNDIGE SORTENBEZEICHNUNGEN nach TL Asphalt-StB 07/13
# =============================================================================

ALLE_ASPHALT_SORTEN: Dict[str, Dict[str, Any]] = {
    # AC Tragschicht
    "AC 32 T S": {"typ": "AC", "groesstkorn_mm": 32, "schicht": "T", "beanspruchung": "S"},
    "AC 22 T S": {"typ": "AC", "groesstkorn_mm": 22, "schicht": "T", "beanspruchung": "S"},
    "AC 16 T S": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "T", "beanspruchung": "S"},
    "AC 32 T N": {"typ": "AC", "groesstkorn_mm": 32, "schicht": "T", "beanspruchung": "N"},
    "AC 22 T N": {"typ": "AC", "groesstkorn_mm": 22, "schicht": "T", "beanspruchung": "N"},
    "AC 16 T N": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "T", "beanspruchung": "N"},
    "AC 32 T L": {"typ": "AC", "groesstkorn_mm": 32, "schicht": "T", "beanspruchung": "L"},
    "AC 22 T L": {"typ": "AC", "groesstkorn_mm": 22, "schicht": "T", "beanspruchung": "L"},
    "AC 16 T L": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "T", "beanspruchung": "L"},
    # AC Tragdeckschicht
    "AC 16 TD": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "TD", "beanspruchung": None},
    # AC Binder
    "AC 22 B S": {"typ": "AC", "groesstkorn_mm": 22, "schicht": "B", "beanspruchung": "S"},
    "AC 16 B S": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "B", "beanspruchung": "S"},
    "AC 16 B N": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "B", "beanspruchung": "N"},
    "AC 11 B N": {"typ": "AC", "groesstkorn_mm": 11, "schicht": "B", "beanspruchung": "N"},
    # AC Deckschicht
    "AC 16 D S": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "D", "beanspruchung": "S"},
    "AC 11 D S": {"typ": "AC", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "S"},
    "AC 8 D S": {"typ": "AC", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "S"},
    "AC 11 D N": {"typ": "AC", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "N"},
    "AC 8 D N": {"typ": "AC", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "N"},
    "AC 11 D L": {"typ": "AC", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "L"},
    "AC 8 D L": {"typ": "AC", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "L"},
    "AC 5 D L": {"typ": "AC", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "L"},
    # SMA (immer Deckschicht)
    "SMA 11 S": {"typ": "SMA", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "S"},
    "SMA 8 S": {"typ": "SMA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "S"},
    "SMA 5 S": {"typ": "SMA", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "S"},
    "SMA 8 N": {"typ": "SMA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "N"},
    "SMA 5 N": {"typ": "SMA", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "N"},
    # MA (immer Deckschicht)
    "MA 11 S": {"typ": "MA", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "S"},
    "MA 8 S": {"typ": "MA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "S"},
    "MA 5 S": {"typ": "MA", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "S"},
    "MA 11 N": {"typ": "MA", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "N"},
    "MA 8 N": {"typ": "MA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "N"},
    "MA 5 N": {"typ": "MA", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "N"},
    # PA (immer Deckschicht)
    "PA 16": {"typ": "PA", "groesstkorn_mm": 16, "schicht": "D", "beanspruchung": None},
    "PA 11": {"typ": "PA", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": None},
    "PA 8": {"typ": "PA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": None},
}


# =============================================================================
# BINDEMITTEL
# =============================================================================

PMB_KEYWORDS = ["PMB", "POLYMER", "MODIFIZIERT", "ELASTOMER",
                "10/40-65", "25/55-55", "45/80-50", "40/100-65"]


# =============================================================================
# AUSSCHLUSSLISTE FÜR EPD-MATCHING
# =============================================================================

AUSSCHLUSS_BEGRIFFE: List[str] = [
    # Betonprodukte
    "Betonpflaster", "Pflasterstein", "Betonstein",
    "Betonsteinpflaster", "Verbundpflaster",
    # Beton mit Festigkeitsklassen
    "C20/25", "C25/30", "C30/37", "C35/45", "C40/50", "C45/55", "C50/60",
    # Andere Nicht-Asphalt-Materialien
    "Mörtel", "Estrich",
    "Kalksandstein", "Mauerwerk", "Ziegel",
    "Anhydrit", "Gips",
    # Hydraulisch gebundene Tragschichten
    "HGT"
]


# =============================================================================
# HAUPT-PARSER: Kombiniert Material + Schichtname
# =============================================================================

def parse_material_input(
    material_name: str,
    schicht_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parst Material-Input und nutzt Schichtname als Fallback.

    Dies ist die HAUPT-FUNKTION für den EPD-Matcher!

    Args:
        material_name: z.B. "AC 16 B S" oder "Aspahltbeton" (auch mit Tippfehlern)
        schicht_name: z.B. "Deckschicht", "Binderschicht" (aus IFC NAME-Feld)

    Returns:
        Dict mit:
        - typ: "AC", "SMA", etc. oder None
        - typ_name: "Asphaltbeton", etc.
        - schicht: "D", "B", "T" oder None
        - schicht_name: "Asphaltdeckschicht", etc.
        - schicht_epd_muss_enthalten: "Deck", "Binder", "Trag"
        - ist_pmb: bool
        - confidence_hint: Hinweis zur Qualität der Erkennung
        - quelle: "bezeichnung", "schichtname", "fuzzy" oder "unbekannt"
    """
    result = {
        "material_original": material_name,
        "schicht_name_original": schicht_name,
        "typ": None,
        "typ_name": None,
        "schicht": None,
        "schicht_name": None,
        "schicht_epd_muss_enthalten": None,
        "groesstkorn_mm": None,
        "beanspruchung": None,
        "ist_pmb": False,
        "ist_asphalt": False,
        "confidence_hint": "",
        "quelle": "unbekannt"
    }

    # Schritt 1: Versuche normierte Bezeichnung zu parsen
    parsed = _parse_normierte_bezeichnung(material_name)
    if parsed:
        result.update(parsed)
        result["quelle"] = "bezeichnung"
        result["ist_asphalt"] = True
        result["confidence_hint"] = "Normierte Bezeichnung erkannt"
        return result

    # Schritt 2: Fuzzy-Match auf Material-Name
    fuzzy_typ = _fuzzy_match_asphalt_type(material_name)
    if fuzzy_typ:
        result["typ"] = fuzzy_typ
        result["typ_name"] = ASPHALT_TYPES[fuzzy_typ]["name_de"]
        result["ist_asphalt"] = True
        result["quelle"] = "fuzzy"

    # Schritt 3: Schicht aus Schichtname ableiten (Fallback!)
    if schicht_name:
        schicht_code = _schicht_aus_name(schicht_name)
        if schicht_code:
            result["schicht"] = schicht_code
            result["schicht_name"] = LAYER_CODES[schicht_code]["name_de"]
            result["schicht_epd_muss_enthalten"] = LAYER_CODES[schicht_code]["epd_muss_enthalten"]
            if result["quelle"] == "unbekannt":
                result["quelle"] = "schichtname"
            result["confidence_hint"] = f"Schicht aus NAME-Feld '{schicht_name}' abgeleitet"

    # Schritt 4: PmB prüfen
    result["ist_pmb"] = _ist_polymermodifiziert(material_name)

    # Schritt 5: Wenn immer noch keine Typ-Info, prüfe auf generische Asphalt-Begriffe
    if not result["ist_asphalt"]:
        if _ist_generisch_asphalt(material_name):
            result["ist_asphalt"] = True
            result["typ"] = "AC"  # Default-Annahme
            result["typ_name"] = "Asphaltbeton (angenommen)"
            result["quelle"] = "fuzzy"
            result["confidence_hint"] = "Generischer Asphalt-Begriff erkannt"

    return result


def _parse_normierte_bezeichnung(bezeichnung: str) -> Optional[Dict[str, Any]]:
    """Parst normierte Asphalt-Bezeichnung wie 'AC 16 B S'."""
    bez = bezeichnung.upper().strip()

    # Pattern: AC/SMA/MA/PA + Zahl + optional Schicht + optional Beanspruchung
    pattern = r"(AC|SMA|MA|PA)\s*(\d+)\s*(TD|T|B|D)?\s*([SNL])?"
    match = re.match(pattern, bez)

    if not match:
        return None

    typ = match.group(1)
    groesstkorn = int(match.group(2))
    schicht = match.group(3)
    beanspruchung = match.group(4)

    # Bei SMA, MA, PA ist Schicht implizit D
    if typ in ["SMA", "MA", "PA"] and not schicht:
        schicht = "D"

    result = {
        "typ": typ,
        "typ_name": ASPHALT_TYPES[typ]["name_de"],
        "groesstkorn_mm": groesstkorn,
        "schicht": schicht,
        "beanspruchung": beanspruchung,
        "ist_pmb": _ist_polymermodifiziert(bezeichnung),
    }

    if schicht:
        result["schicht_name"] = LAYER_CODES[schicht]["name_de"]
        result["schicht_epd_muss_enthalten"] = LAYER_CODES[schicht]["epd_muss_enthalten"]

    if beanspruchung:
        result["beanspruchung_name"] = LOAD_CLASSES[beanspruchung]["name_de"]

    return result


def _fuzzy_match_asphalt_type(text: str) -> Optional[str]:
    """Versucht Asphalt-Typ aus Text zu erkennen (auch bei Tippfehlern)."""
    text_lower = text.lower()

    for typ_code, typ_info in ASPHALT_TYPES.items():
        for fuzzy in typ_info.get("fuzzy_matches", []):
            if fuzzy in text_lower:
                return typ_code

    return None


def _schicht_aus_name(schicht_name: str) -> Optional[str]:
    """Leitet Schichtcode aus Schichtname ab."""
    name_lower = schicht_name.lower()

    for code, info in LAYER_CODES.items():
        for variante in info.get("name_varianten", []):
            if variante in name_lower:
                return code

    return None


def _ist_polymermodifiziert(text: str) -> bool:
    """Prüft ob Text auf PmB hinweist."""
    text_upper = text.upper()
    return any(kw in text_upper for kw in PMB_KEYWORDS)


def _ist_generisch_asphalt(text: str) -> bool:
    """Prüft ob Text generisch auf Asphalt hinweist."""
    asphalt_keywords = [
        "asphalt", "aspahlt",  # inkl. Tippfehler
        "bitumen", "bituminös", "bituminos",
        "schwarzdecke", "heißmischgut"
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in asphalt_keywords)


# =============================================================================
# EPD-VORFILTERUNG
# =============================================================================

def filter_epds_for_material(
    epds: List[Dict[str, Any]],
    parsed_material: Dict[str, Any],
    max_epds: int = 100
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Filtert EPD-Liste basierend auf parsed Material.

    Args:
        epds: Alle verfügbaren EPDs
        parsed_material: Output von parse_material_input()
        max_epds: Maximale Anzahl zurückzugebender EPDs

    Returns:
        Tuple: (primäre_matches, sekundäre_matches)
        - primäre: Schicht + Typ stimmen
        - sekundäre: Nur Typ stimmt
    """
    if not parsed_material.get("ist_asphalt"):
        # Kein Asphalt erkannt -> alle EPDs durchreichen
        return epds[:max_epds], []

    schicht_muss = parsed_material.get("schicht_epd_muss_enthalten", "").lower()
    typ_begriffe = []
    if parsed_material.get("typ"):
        typ_begriffe = [b.lower() for b in ASPHALT_TYPES[parsed_material["typ"]]["suchbegriffe"]]

    primaer = []
    sekundaer = []

    for epd in epds:
        epd_name = epd.get("name", "").lower()
        epd_klassifizierung = epd.get("klassifizierung", "").lower()
        combined = f"{epd_name} {epd_klassifizierung}"

        # Ausschluss prüfen
        if _ist_ausgeschlossen(combined):
            continue

        # Ist es überhaupt Asphalt?
        if not _ist_generisch_asphalt(combined) and not any(t in combined for t in typ_begriffe):
            continue

        # Schicht-Match?
        schicht_match = schicht_muss and schicht_muss in combined

        if schicht_match:
            primaer.append(epd)
        else:
            sekundaer.append(epd)

    # Limit anwenden
    if len(primaer) >= max_epds:
        return primaer[:max_epds], []

    remaining = max_epds - len(primaer)
    return primaer, sekundaer[:remaining]


def _ist_ausgeschlossen(text: str) -> bool:
    """Prüft ob Text einen Ausschluss-Begriff enthält."""
    text_lower = text.lower()
    return any(excl.lower() in text_lower for excl in AUSSCHLUSS_BEGRIFFE)


# =============================================================================
# SUCHBEGRIFFE FÜR MATCHING
# =============================================================================

def get_suchbegriffe_fuer_matching(parsed_material: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Generiert Suchbegriffe basierend auf parsed Material.

    Returns:
        Dict mit:
        - typ: Typ-Suchbegriffe
        - schicht: Schicht-Suchbegriffe
        - pmb: PmB-Begriffe falls relevant
        - alle: Kombiniert
    """
    result = {"typ": [], "schicht": [], "pmb": [], "alle": []}

    if parsed_material.get("typ"):
        result["typ"] = ASPHALT_TYPES[parsed_material["typ"]]["suchbegriffe"]

    if parsed_material.get("schicht"):
        result["schicht"] = LAYER_CODES[parsed_material["schicht"]]["suchbegriffe"]

    if parsed_material.get("ist_pmb"):
        result["pmb"] = ["polymermodifiziert", "PmB", "Elastomer", "modifiziert"]

    result["alle"] = list(set(result["typ"] + result["schicht"] + result["pmb"]))

    return result


# =============================================================================
# PROMPT-GENERIERUNG
# =============================================================================

def generate_material_context(material_name: str, schicht_name: Optional[str] = None) -> str:
    """
    Generiert kompakten Kontext-String für GPT-Prompt.

    Args:
        material_name: Material-Bezeichnung
        schicht_name: Optionaler Schichtname aus IFC

    Returns:
        Kontext-String für Prompt
    """
    parsed = parse_material_input(material_name, schicht_name)

    if not parsed.get("ist_asphalt"):
        return f"Material: {material_name} (kein Asphalt erkannt)"

    parts = []

    if parsed.get("typ"):
        parts.append(f"{parsed['typ']}={parsed['typ_name']}")

    if parsed.get("schicht"):
        parts.append(f"{parsed['schicht']}={parsed['schicht_name']}")
        if parsed.get("schicht_epd_muss_enthalten"):
            parts.append(f"EPD muss '{parsed['schicht_epd_muss_enthalten']}' enthalten")

    if parsed.get("beanspruchung"):
        parts.append(f"{parsed['beanspruchung']}={LOAD_CLASSES[parsed['beanspruchung']]['name_de']}")

    if parsed.get("ist_pmb"):
        parts.append("PmB vorhanden")

    if parsed.get("confidence_hint"):
        parts.append(f"[{parsed['confidence_hint']}]")

    return ", ".join(parts) if parts else f"Material: {material_name}"


def generate_prompt_glossary() -> str:
    """Generiert kompaktes Glossar für GPT-Prompt."""
    return """
╔════════════════════════════════════════════════════════════════════╗
║  ASPHALT-BEZEICHNUNGEN NACH TL ASPHALT-STB 07/13                  ║
╚════════════════════════════════════════════════════════════════════╝

📋 AUFBAU: [TYP] [GRÖSSKORN] [SCHICHT] [BEANSPRUCHUNG]
   Beispiel: AC 16 B S = Asphaltbeton, 16mm, Binder, spezial

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  ASPHALT-TYPEN
  AC   = Asphaltbeton         → Asphalt, Bitumen, bituminös
  SMA  = Splittmastixasphalt  → Splittmastix, SMA
  MA   = Gussasphalt          → Gussasphalt, Mastic
  PA   = Offenporiger Asphalt → Drainasphalt, OPA

2️⃣  SCHICHTCODES (⚠️ KRITISCH!)
  D  = Deckschicht   → EPD muss "Deck" enthalten
  B  = Binder        → EPD muss "Binder" enthalten
  T  = Tragschicht   → EPD muss "Trag" enthalten
  TD = Tragdeck      → EPD muss "Tragdeck" enthalten

3️⃣  BEANSPRUCHUNG
  S = schwer (Autobahnen), N = normal, L = leicht (Radwege)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 CONFIDENCE-REGELN:
  85-100%: Korrekter SCHICHT-Begriff + TYP im EPD-Namen
  60-84%:  Korrekter SCHICHT-Begriff + Asphalt-Bezug
  40-49%:  Asphalt-Bezug, aber FALSCHER Schicht-Begriff
  <30%:    Ausschluss-Begriff → NICHT LISTEN!

❌ AUSSCHLUSS: Betonpflaster, Zement, Mörtel, C20/25, Kalksandstein...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


# =============================================================================
# LEGACY-FUNKTIONEN (Rückwärtskompatibilität)
# =============================================================================

def parse_asphalt_bezeichnung(bezeichnung: str) -> Optional[Dict[str, Any]]:
    """Legacy-Funktion. Nutze stattdessen parse_material_input()."""
    result = parse_material_input(bezeichnung, None)
    if result.get("ist_asphalt"):
        return result
    return None


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("ASPHALT-GLOSSAR TEST")
    print("=" * 70)

    test_cases = [
        # (Material, Schichtname)
        ("AC 11 D S", None),
        ("AC 16 B S SG mit Polymermodifiziertem Bindemittel 10/40-65A", None),
        ("Aspahltbeton", "Deckschicht"),  # Tippfehler + Fallback!
        ("Asphalt", "Binderschicht"),
        ("SMA 11 S", None),
        ("Bituminöse Schicht", "Tragschicht"),
        ("Unbekanntes Material", None),
    ]

    for material, schicht in test_cases:
        print(f"\nMaterial: {material}")
        if schicht:
            print(f"Schicht:  {schicht}")

        result = parse_material_input(material, schicht)
        context = generate_material_context(material, schicht)

        print(f"→ {context}")
        print(f"  Quelle: {result['quelle']}, Asphalt: {result['ist_asphalt']}")

    print("\n" + "=" * 70)