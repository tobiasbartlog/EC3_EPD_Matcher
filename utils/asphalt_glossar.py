"""
Asphalt-Glossar für EPD-Matching - FIXED VERSION
================================================

FIX: filter_epds_for_material filtert jetzt auch Nicht-Asphalt-Materialien!
- Schotter/Kies → nur Schotter/Kies EPDs
- XPS/Dämmung → nur Dämm-EPDs
- Unbekannt → Keyword-basierte Suche

Basierend auf: TL Asphalt-StB 07/13
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
    "S": {"name_de": "besondere Beanspruchung", "kurzform": "besondere"},
    "N": {"name_de": "normale Beanspruchung", "kurzform": "normal"},
    "L": {"name_de": "leichte Beanspruchung", "kurzform": "leicht"},
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
    "Betonpflaster", "Pflasterstein", "Betonstein",
    "Betonsteinpflaster", "Verbundpflaster",
    "C20/25", "C25/30", "C30/37", "C35/45", "C40/50", "C45/55", "C50/60",
    "Mörtel", "Estrich",
    "Kalksandstein", "Mauerwerk", "Ziegel",
    "Anhydrit", "Gips",
    "HGT"
]


# =============================================================================
# NEU: MATERIAL-KATEGORIEN FÜR NICHT-ASPHALT
# =============================================================================

MATERIAL_KATEGORIEN: Dict[str, Dict[str, Any]] = {
    "schotter": {
        "keywords": ["schotter", "kies", "splitt", "gestein", "mineralgemisch",
                    "gesteinskörnung", "naturstein", "brechsand", "edelsplitt"],
        "suchbegriffe": ["schotter", "kies", "splitt", "gestein", "mineral",
                        "gesteinskörnung", "naturstein", "brechsand", "sand",
                        "rundkies", "edelsplitt", "bims"],
        "ausschluss": ["asphalt", "bitumen", "dämmung", "xps", "eps", "beton",
                      "bitumenbahn", "abdichtung"]
    },
    "frostschutz": {
        "keywords": ["frostschutz", "fsts", "fsks", "fsk"],
        "suchbegriffe": ["frostschutz", "kies", "sand", "mineral", "tragschicht",
                        "schotter", "kiessand"],
        "ausschluss": ["asphalt", "bitumen", "dämmung", "bitumenbahn"]
    },
    "daemmung": {
        "keywords": ["xps", "eps", "dämmung", "dämm", "isolierung", "pur", "pir",
                    "mineralwolle", "steinwolle", "glaswolle", "polystyrol",
                    "wärmedämmung", "perimeterdämmung"],
        "suchbegriffe": ["xps", "eps", "dämmung", "dämm", "polystyrol", "isolier",
                        "wärme", "mineralwolle", "steinwolle", "schaum", "styro",
                        "perimeter", "extrudiert"],
        "ausschluss": ["asphalt", "bitumen", "schotter", "kies", "beton",
                      "bitumenbahn", "pflaster"]
    },
    "abdichtung": {
        "keywords": ["abdichtung", "bitumenbahn", "dachbahn", "schweißbahn"],
        "suchbegriffe": ["abdichtung", "bitumenbahn", "dachbahn", "schweißbahn",
                        "dachabdichtung", "bauwerksabdichtung"],
        "ausschluss": ["asphalt", "schotter", "dämmung", "pflaster"]
    },
}


# =============================================================================
# HAUPT-PARSER
# =============================================================================

def parse_material_input(
    material_name: str,
    schicht_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parst Material-Input und nutzt Schichtname als Fallback.
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

    # Schritt 3: Schicht aus Schichtname ableiten
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

    # Schritt 5: Generische Asphalt-Begriffe
    if not result["ist_asphalt"]:
        if _ist_generisch_asphalt(material_name):
            result["ist_asphalt"] = True
            result["typ"] = "AC"
            result["typ_name"] = "Asphaltbeton (angenommen)"
            result["quelle"] = "fuzzy"
            result["confidence_hint"] = "Generischer Asphalt-Begriff erkannt"

    return result


def _parse_normierte_bezeichnung(bezeichnung: str) -> Optional[Dict[str, Any]]:
    """Parst normierte Asphalt-Bezeichnung wie 'AC 16 B S'."""
    bez = bezeichnung.upper().strip()
    pattern = r"(AC|SMA|MA|PA)\s*(\d+)\s*(TD|T|B|D)?\s*([SNL])?"
    match = re.match(pattern, bez)

    if not match:
        return None

    typ = match.group(1)
    groesstkorn = int(match.group(2))
    schicht = match.group(3)
    beanspruchung = match.group(4)

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
    """Versucht Asphalt-Typ aus Text zu erkennen."""
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
        "asphalt", "aspahlt", "bitumen", "bituminös", "bituminos",
        "schwarzdecke", "heißmischgut"
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in asphalt_keywords)


def _ist_ausgeschlossen(text: str) -> bool:
    """Prüft ob Text einen Ausschluss-Begriff enthält."""
    text_lower = text.lower()
    return any(excl.lower() in text_lower for excl in AUSSCHLUSS_BEGRIFFE)


# =============================================================================
# NEU: Kategorie-Erkennung für Nicht-Asphalt
# =============================================================================

def _detect_material_category(material_name: str, schicht_name: str) -> Optional[str]:
    """Erkennt Material-Kategorie aus Name."""
    combined = f"{material_name} {schicht_name}".lower()

    for category, info in MATERIAL_KATEGORIEN.items():
        if any(kw in combined for kw in info["keywords"]):
            return category

    return None


# =============================================================================
# VERBESSERTE EPD-VORFILTERUNG
# =============================================================================

def filter_epds_for_material(
    epds: List[Dict[str, Any]],
    parsed_material: Dict[str, Any],
    max_epds: int = 100
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Filtert EPD-Liste basierend auf parsed Material.

    VERBESSERT: Filtert jetzt auch Nicht-Asphalt-Materialien!

    Args:
        epds: Alle verfügbaren EPDs
        parsed_material: Output von parse_material_input()
        max_epds: Maximale Anzahl zurückzugebender EPDs

    Returns:
        Tuple: (primäre_matches, sekundäre_matches)
    """
    material_orig = parsed_material.get("material_original", "")
    schicht_orig = parsed_material.get("schicht_name_original", "") or ""

    # =========================================================================
    # FALL 1: Asphalt erkannt
    # =========================================================================
    if parsed_material.get("ist_asphalt"):
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

            if _ist_ausgeschlossen(combined):
                continue

            ist_asphalt = _ist_generisch_asphalt(combined) or any(t in combined for t in typ_begriffe)

            if not ist_asphalt:
                continue

            schicht_match = schicht_muss and schicht_muss in combined

            if schicht_match:
                primaer.append(epd)
            else:
                sekundaer.append(epd)

        if len(primaer) >= max_epds:
            return primaer[:max_epds], []

        remaining = max_epds - len(primaer)
        return primaer, sekundaer[:remaining]

    # =========================================================================
    # FALL 2: Nicht-Asphalt -> Kategorie-basierte Filterung
    # =========================================================================
    category = _detect_material_category(material_orig, schicht_orig)

    if category and category in MATERIAL_KATEGORIEN:
        cat_info = MATERIAL_KATEGORIEN[category]
        suchbegriffe = [s.lower() for s in cat_info["suchbegriffe"]]
        ausschluss = [a.lower() for a in cat_info["ausschluss"]]

        primaer = []
        sekundaer = []

        for epd in epds:
            epd_name = epd.get("name", "").lower()
            epd_klassifizierung = epd.get("klassifizierung", "").lower()
            combined = f"{epd_name} {epd_klassifizierung}"

            # Globale Ausschlüsse
            if _ist_ausgeschlossen(combined):
                continue

            # Kategorie-spezifische Ausschlüsse
            if any(excl in combined for excl in ausschluss):
                continue

            # Suche nach Kategorie-Begriffen
            if any(such in combined for such in suchbegriffe):
                primaer.append(epd)

        # Fallback: Suche nach Material-Name direkt
        if len(primaer) < 10:
            material_words = [w for w in material_orig.lower().split() if len(w) > 3]
            for epd in epds:
                if epd in primaer:
                    continue
                epd_name = epd.get("name", "").lower()
                if any(word in epd_name for word in material_words):
                    sekundaer.append(epd)

        if len(primaer) >= max_epds:
            return primaer[:max_epds], []

        remaining = max_epds - len(primaer)
        return primaer, sekundaer[:remaining]

    # =========================================================================
    # FALL 3: Unbekanntes Material -> Keyword-Suche
    # =========================================================================
    stop_words = {"mit", "und", "für", "der", "die", "das", "von", "nach", "gemäß"}
    material_words = [
        w.lower() for w in f"{material_orig} {schicht_orig}".split()
        if len(w) > 2 and w.lower() not in stop_words
    ]

    if not material_words:
        return epds[:min(50, max_epds)], []

    primaer = []
    for epd in epds:
        epd_name = epd.get("name", "").lower()
        epd_klassifizierung = epd.get("klassifizierung", "").lower()
        combined = f"{epd_name} {epd_klassifizierung}"

        if _ist_ausgeschlossen(combined):
            continue

        if any(word in combined for word in material_words):
            primaer.append(epd)

    return primaer[:max_epds], []


# =============================================================================
# SUCHBEGRIFFE FÜR MATCHING
# =============================================================================

def get_suchbegriffe_fuer_matching(parsed_material: Dict[str, Any]) -> Dict[str, List[str]]:
    """Generiert Suchbegriffe basierend auf parsed Material."""
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
    """Generiert kompakten Kontext-String für GPT-Prompt."""
    parsed = parse_material_input(material_name, schicht_name)

    if not parsed.get("ist_asphalt"):
        # Prüfe auf andere Kategorien
        category = _detect_material_category(material_name, schicht_name or "")
        if category:
            return f"Kategorie: {category.upper()}, Material: {material_name}"
        return f"Material: {material_name} (Typ unbekannt)"

    parts = []

    if parsed.get("typ"):
        parts.append(f"{parsed['typ']}={parsed['typ_name']}")

    if parsed.get("schicht"):
        parts.append(f"{parsed['schicht']}={parsed['schicht_name']}")
        if parsed.get("schicht_epd_muss_enthalten"):
            parts.append(f"EPD sollte '{parsed['schicht_epd_muss_enthalten']}' enthalten")

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
ASPHALT-CODES: AC=Asphaltbeton, SMA=Splittmastix, MA=Gussasphalt, PA=Offenporig
SCHICHTEN: D=Deckschicht, B=Binder, T=Tragschicht
BEANSPRUCHUNG: S=schwer, N=normal, L=leicht
"""


# =============================================================================
# LEGACY-FUNKTIONEN
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
    print("ASPHALT-GLOSSAR TEST (FIXED)")
    print("=" * 70)

    test_cases = [
        ("AC 11 D S", None),
        ("AC 16 B S SG mit Polymermodifiziertem Bindemittel", None),
        ("Aspahltbeton", "Deckschicht"),
        ("A4-Schottertragschicht 0/45", "Schottertrag"),
        ("XPS", "Wärmedämmung"),
        ("Unbekanntes Material", None),
    ]

    for material, schicht in test_cases:
        print(f"\n{'-'*50}")
        print(f"Material: {material}")
        if schicht:
            print(f"Schicht:  {schicht}")

        result = parse_material_input(material, schicht)
        context = generate_material_context(material, schicht)
        category = _detect_material_category(material, schicht or "")

        print(f"→ {context}")
        print(f"  Asphalt: {result['ist_asphalt']}, Kategorie: {category}")

    print("\n" + "=" * 70)