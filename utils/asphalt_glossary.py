"""
Asphalt-Glossar für EPD-Matching
================================
Basierend auf: TL Asphalt-StB 07/13 (Technische Lieferbedingungen für Asphaltmischgut
für den Bau von Verkehrsflächenbefestigungen, Ausgabe 2007/Fassung 2013)

Verwendung:
    from utils.asphalt_glossar import (
        parse_asphalt_bezeichnung,
        get_suchbegriffe_fuer_bezeichnung,
        generate_prompt_glossary,
        AUSSCHLUSS_BEGRIFFE
    )
"""

import re
from typing import Dict, List, Optional, Any


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
        ]
    },
    "SMA": {
        "name_de": "Splittmastixasphalt",
        "name_en": "Stone Mastic Asphalt",
        "norm": "DIN EN 13108-5",
        "beschreibung": "Asphaltmischgut mit Ausfallkörnung und Zusätzen als Bindemittelträger",
        "suchbegriffe": [
            "Splittmastixasphalt", "Splittmastix", "SMA",
            "Stone Mastic", "Mastixasphalt"
        ]
    },
    "MA": {
        "name_de": "Gussasphalt",
        "name_en": "Mastic Asphalt",
        "norm": "DIN EN 13108-6",
        "beschreibung": "Dichtes Asphaltmischgut, im heißen Zustand gießbar und streichfähig",
        "suchbegriffe": [
            "Gussasphalt", "Mastic Asphalt", "Asphaltmastix",
            "Gießasphalt", "MA"
        ]
    },
    "PA": {
        "name_de": "Offenporiger Asphalt",
        "name_en": "Porous Asphalt",
        "norm": "DIN EN 13108-7",
        "beschreibung": "Asphaltmischgut mit sehr hohem Anteil an miteinander verbundenen Hohlräumen",
        "suchbegriffe": [
            "Offenporiger Asphalt", "OPA", "Drainasphalt",
            "Porous Asphalt", "Drainageschicht", "lärmmindernd",
            "Flüsterasphalt", "PA"
        ]
    }
}


# =============================================================================
# SCHICHTCODES (Nationale Ergänzung Deutschland)
# =============================================================================

LAYER_CODES: Dict[str, Dict[str, Any]] = {
    "T": {
        "name_de": "Asphalttragschicht",
        "kurzform": "Tragschicht",
        "beschreibung": "Unterste Asphaltschicht, trägt Verkehrslasten ab",
        "position": "unten",
        "epd_muss_enthalten": "Trag",
        "suchbegriffe": [
            "Asphalttragschicht", "Tragschicht", "Asphalt-Tragschicht",
            "bituminöse Tragschicht", "ATS"
        ]
    },
    "B": {
        "name_de": "Asphaltbinder",
        "kurzform": "Binderschicht",
        "beschreibung": "Mittlere Asphaltschicht zwischen Trag- und Deckschicht",
        "position": "mitte",
        "epd_muss_enthalten": "Binder",
        "suchbegriffe": [
            "Asphaltbinder", "Binderschicht", "Asphaltbinderschicht",
            "Binder", "ABi"
        ]
    },
    "D": {
        "name_de": "Asphaltdeckschicht",
        "kurzform": "Deckschicht",
        "beschreibung": "Oberste Asphaltschicht, direkt befahren",
        "position": "oben",
        "epd_muss_enthalten": "Deck",
        "suchbegriffe": [
            "Asphaltdeckschicht", "Deckschicht", "Asphalt-Deckschicht",
            "Verschleißschicht", "Fahrbahndecke", "ADS", "Decke"
        ]
    },
    "TD": {
        "name_de": "Asphalttragdeckschicht",
        "kurzform": "Tragdeckschicht",
        "beschreibung": "Kombinierte Trag- und Deckschicht für geringere Belastungen",
        "position": "kombiniert",
        "epd_muss_enthalten": "Tragdeck",
        "suchbegriffe": [
            "Asphalttragdeckschicht", "Tragdeckschicht",
            "kombinierte Schicht", "ATDS"
        ]
    }
}


# =============================================================================
# BEANSPRUCHUNGSKLASSEN
# =============================================================================

LOAD_CLASSES: Dict[str, Dict[str, Any]] = {
    "S": {
        "name_de": "besondere Beanspruchung",
        "kurzform": "schwer",
        "beschreibung": "Für Verkehrsflächen mit besonderer/schwerer Beanspruchung",
        "anwendung": ["Autobahnen", "Bundesstraßen", "Industrieflächen"],
        "bauklassen_rstO": ["Bk100", "Bk32", "Bk10"]
    },
    "N": {
        "name_de": "normale Beanspruchung",
        "kurzform": "normal",
        "beschreibung": "Für Verkehrsflächen mit normaler Beanspruchung",
        "anwendung": ["Landesstraßen", "Kreisstraßen", "Hauptverkehrsstraßen"],
        "bauklassen_rstO": ["Bk3.2", "Bk1.8", "Bk1.0"]
    },
    "L": {
        "name_de": "leichte Beanspruchung",
        "kurzform": "leicht",
        "beschreibung": "Für Verkehrsflächen mit leichter Beanspruchung",
        "anwendung": ["Wohnstraßen", "Radwege", "Parkplätze", "Gehwege"],
        "bauklassen_rstO": ["Bk0.3", "Bk0.0"]
    }
}


# =============================================================================
# VOLLSTÄNDIGE SORTENBEZEICHNUNGEN nach TL Asphalt-StB 07/13
# =============================================================================

ALLE_ASPHALT_SORTEN: Dict[str, Dict[str, Any]] = {
    # ===== Asphalttragschichtmischgut (AC T) =====
    # Besondere Beanspruchung (S)
    "AC 32 T S": {"typ": "AC", "groesstkorn_mm": 32, "schicht": "T", "beanspruchung": "S",
                  "bindemittel": ["50/70", "30/45"], "min_bindemittelgehalt": 3.8},
    "AC 22 T S": {"typ": "AC", "groesstkorn_mm": 22, "schicht": "T", "beanspruchung": "S",
                  "bindemittel": ["50/70", "30/45"], "min_bindemittelgehalt": 3.8},
    "AC 16 T S": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "T", "beanspruchung": "S",
                  "bindemittel": ["50/70", "30/45"], "min_bindemittelgehalt": 4.0},
    # Normale Beanspruchung (N)
    "AC 32 T N": {"typ": "AC", "groesstkorn_mm": 32, "schicht": "T", "beanspruchung": "N",
                  "bindemittel": ["70/100", "50/70"], "min_bindemittelgehalt": 4.0},
    "AC 22 T N": {"typ": "AC", "groesstkorn_mm": 22, "schicht": "T", "beanspruchung": "N",
                  "bindemittel": ["70/100", "50/70"], "min_bindemittelgehalt": 4.0},
    "AC 16 T N": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "T", "beanspruchung": "N",
                  "bindemittel": ["70/100", "50/70"], "min_bindemittelgehalt": 4.0},
    # Leichte Beanspruchung (L)
    "AC 32 T L": {"typ": "AC", "groesstkorn_mm": 32, "schicht": "T", "beanspruchung": "L",
                  "bindemittel": ["70/100"], "min_bindemittelgehalt": 4.0},
    "AC 22 T L": {"typ": "AC", "groesstkorn_mm": 22, "schicht": "T", "beanspruchung": "L",
                  "bindemittel": ["70/100"], "min_bindemittelgehalt": 4.0},
    "AC 16 T L": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "T", "beanspruchung": "L",
                  "bindemittel": ["70/100"], "min_bindemittelgehalt": 4.2},

    # ===== Asphalttragdeckschichtmischgut (AC TD) =====
    "AC 16 TD": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "TD", "beanspruchung": None,
                 "bindemittel": ["70/100", "50/70", "160/220"], "min_bindemittelgehalt": 5.4},

    # ===== Asphaltbinder (AC B) =====
    # Besondere Beanspruchung (S)
    "AC 22 B S": {"typ": "AC", "groesstkorn_mm": 22, "schicht": "B", "beanspruchung": "S",
                  "bindemittel": ["25/55-55", "30/45", "10/40-65"], "min_bindemittelgehalt": 4.2},
    "AC 16 B S": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "B", "beanspruchung": "S",
                  "bindemittel": ["25/55-55", "30/45", "10/40-65"], "min_bindemittelgehalt": 4.4},
    # Normale Beanspruchung (N)
    "AC 16 B N": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "B", "beanspruchung": "N",
                  "bindemittel": ["50/70", "30/45"], "min_bindemittelgehalt": 4.4},
    "AC 11 B N": {"typ": "AC", "groesstkorn_mm": 11, "schicht": "B", "beanspruchung": "N",
                  "bindemittel": ["50/70"], "min_bindemittelgehalt": 4.6},

    # ===== Asphaltbeton für Deckschichten (AC D) =====
    # Besondere Beanspruchung (S)
    "AC 16 D S": {"typ": "AC", "groesstkorn_mm": 16, "schicht": "D", "beanspruchung": "S",
                  "bindemittel": ["25/55-55", "50/70", "10/40-65"], "min_bindemittelgehalt": 5.4},
    "AC 11 D S": {"typ": "AC", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "S",
                  "bindemittel": ["25/55-55", "50/70"], "min_bindemittelgehalt": 6.0},
    "AC 8 D S": {"typ": "AC", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "S",
                 "bindemittel": ["25/55-55", "50/70"], "min_bindemittelgehalt": 6.2},
    # Normale Beanspruchung (N)
    "AC 11 D N": {"typ": "AC", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "N",
                  "bindemittel": ["50/70", "70/100"], "min_bindemittelgehalt": 6.2},
    "AC 8 D N": {"typ": "AC", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "N",
                 "bindemittel": ["50/70", "70/100"], "min_bindemittelgehalt": 6.4},
    # Leichte Beanspruchung (L)
    "AC 11 D L": {"typ": "AC", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "L",
                  "bindemittel": ["70/100", "50/70"], "min_bindemittelgehalt": 6.4},
    "AC 8 D L": {"typ": "AC", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "L",
                 "bindemittel": ["70/100"], "min_bindemittelgehalt": 6.6},
    "AC 5 D L": {"typ": "AC", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "L",
                 "bindemittel": ["70/100"], "min_bindemittelgehalt": 7.0},

    # ===== Splittmastixasphalt (SMA) =====
    # Besondere Beanspruchung (S)
    "SMA 11 S": {"typ": "SMA", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "S",
                 "bindemittel": ["25/55-55", "50/70"], "min_bindemittelgehalt": 6.6},
    "SMA 8 S": {"typ": "SMA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "S",
                "bindemittel": ["25/55-55", "50/70"], "min_bindemittelgehalt": 7.2},
    "SMA 5 S": {"typ": "SMA", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "S",
                "bindemittel": ["45/80-50", "50/70", "25/55-55"], "min_bindemittelgehalt": 7.4},
    # Normale Beanspruchung (N)
    "SMA 8 N": {"typ": "SMA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "N",
                "bindemittel": ["50/70", "70/100", "45/80-50"], "min_bindemittelgehalt": 7.2},
    "SMA 5 N": {"typ": "SMA", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "N",
                "bindemittel": ["50/70", "70/100", "45/80-50"], "min_bindemittelgehalt": 7.4},

    # ===== Gussasphalt (MA) =====
    # Besondere Beanspruchung (S)
    "MA 11 S": {"typ": "MA", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "S",
                "bindemittel": ["20/30", "30/45", "10/40-65", "25/55-55"], "min_bindemittelgehalt": 6.8},
    "MA 8 S": {"typ": "MA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "S",
               "bindemittel": ["20/30", "30/45", "10/40-65", "25/55-55"], "min_bindemittelgehalt": 7.0},
    "MA 5 S": {"typ": "MA", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "S",
               "bindemittel": ["20/30", "30/45", "10/40-65", "25/55-55"], "min_bindemittelgehalt": 7.0},
    # Normale Beanspruchung (N)
    "MA 11 N": {"typ": "MA", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": "N",
                "bindemittel": ["30/45", "25/55-55"], "min_bindemittelgehalt": 6.8},
    "MA 8 N": {"typ": "MA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": "N",
               "bindemittel": ["30/45", "25/55-55"], "min_bindemittelgehalt": 7.0},
    "MA 5 N": {"typ": "MA", "groesstkorn_mm": 5, "schicht": "D", "beanspruchung": "N",
               "bindemittel": ["30/45", "25/55-55"], "min_bindemittelgehalt": 7.5},

    # ===== Offenporiger Asphalt (PA) =====
    "PA 16": {"typ": "PA", "groesstkorn_mm": 16, "schicht": "D", "beanspruchung": None,
              "bindemittel": ["40/100-65"], "min_bindemittelgehalt": 5.5},
    "PA 11": {"typ": "PA", "groesstkorn_mm": 11, "schicht": "D", "beanspruchung": None,
              "bindemittel": ["40/100-65"], "min_bindemittelgehalt": 6.0},
    "PA 8": {"typ": "PA", "groesstkorn_mm": 8, "schicht": "D", "beanspruchung": None,
             "bindemittel": ["40/100-65"], "min_bindemittelgehalt": 6.5},
}


# =============================================================================
# BINDEMITTEL
# =============================================================================

STRASSENBAUBITUMEN: Dict[str, Dict[str, Any]] = {
    "20/30": {"haerte": "sehr hart", "verwendung": ["Gussasphalt"]},
    "30/45": {"haerte": "hart", "verwendung": ["Asphaltbinder S", "Gussasphalt", "Asphalttragschicht S"]},
    "50/70": {"haerte": "mittel", "verwendung": ["Asphaltbinder", "Asphaltdeckschicht", "Asphalttragschicht", "SMA"]},
    "70/100": {"haerte": "weich", "verwendung": ["Asphaltdeckschicht N/L", "Asphalttragschicht N/L", "SMA N"]},
    "160/220": {"haerte": "sehr weich", "verwendung": ["Asphalttragdeckschicht"]},
}

POLYMERMODIFIZIERTE_BITUMEN: Dict[str, Dict[str, Any]] = {
    "10/40-65": {"typ": "PmB A", "verwendung": ["Asphaltbinder S", "Gussasphalt S"]},
    "25/55-55": {"typ": "PmB A", "verwendung": ["Asphaltbinder S", "Asphaltdeckschicht S", "SMA S", "Gussasphalt"]},
    "45/80-50": {"typ": "PmB A", "verwendung": ["SMA"]},
    "40/100-65": {"typ": "PmB A", "verwendung": ["Offenporiger Asphalt (PA)"]},
}

PMB_SUCHBEGRIFFE = ["polymermodifiziert", "PmB", "Elastomer", "modifiziert", "Polymer-Bitumen"]


# =============================================================================
# AUSSCHLUSSLISTE FÜR EPD-MATCHING
# =============================================================================

AUSSCHLUSS_BEGRIFFE: List[str] = [
    # Betonprodukte (KEIN Asphalt!)
    "Betonpflaster", "Pflasterstein", "Betonstein",
    "Betonsteinpflaster", "Verbundpflaster",
    # Normaler Beton mit Festigkeitsklassen
    "C20/25", "C25/30", "C30/37", "C35/45", "C40/50", "C45/55", "C50/60",
    # Andere Nicht-Asphalt-Materialien
    "Zement", "Mörtel", "Estrich",
    "Kalksandstein", "Mauerwerk", "Ziegel",
    "Anhydrit", "Gips",
    # Hydraulisch gebundene Tragschichten (kein Asphalt)
    "HGT", "Hydraulisch gebunden",
    # Schotter/Kies ohne Bindemittel
    "Frostschutzschicht", "Schottertragschicht"
]


# =============================================================================
# PARSER-FUNKTIONEN
# =============================================================================

def parse_asphalt_bezeichnung(bezeichnung: str) -> Optional[Dict[str, Any]]:
    """
    Parst eine Asphaltbezeichnung und gibt strukturierte Informationen zurück.

    Args:
        bezeichnung: z.B. "AC 16 B S", "SMA 11 S", "AC 16 B S SG mit Polymermodifiziertem Bindemittel 10/40-65A"

    Returns:
        Dict mit typ, groesstkorn, schicht, beanspruchung, ist_pmb oder None
    """
    # Normalisieren
    bez = bezeichnung.upper().strip()

    # Pattern für Asphaltbezeichnungen
    # Gruppe 1: Typ (AC, SMA, MA, PA)
    # Gruppe 2: Größtkorn (Zahl)
    # Gruppe 3: Schichtcode (T, B, D, TD) - optional bei SMA/MA/PA
    # Gruppe 4: Beanspruchung (S, N, L) - optional
    pattern = r"(AC|SMA|MA|PA)\s*(\d+)\s*(TD|T|B|D)?\s*([SNL])?"

    match = re.match(pattern, bez)
    if not match:
        return None

    typ = match.group(1)
    groesstkorn = int(match.group(2))
    schicht = match.group(3) if match.group(3) else None
    beanspruchung = match.group(4) if match.group(4) else None

    # Bei SMA, MA, PA ist die Schicht implizit D (Deckschicht)
    if typ in ["SMA", "MA", "PA"] and schicht is None:
        schicht = "D"

    # Prüfe auf PmB
    ist_pmb = _ist_polymermodifiziert(bezeichnung)

    return {
        "bezeichnung_original": bezeichnung,
        "bezeichnung_parsed": f"{typ} {groesstkorn} {schicht or ''} {beanspruchung or ''}".strip(),
        "typ": typ,
        "typ_name": ASPHALT_TYPES.get(typ, {}).get("name_de", "Unbekannt"),
        "groesstkorn_mm": groesstkorn,
        "schicht": schicht,
        "schicht_name": LAYER_CODES.get(schicht, {}).get("name_de", "Unbekannt") if schicht else None,
        "schicht_epd_muss_enthalten": LAYER_CODES.get(schicht, {}).get("epd_muss_enthalten") if schicht else None,
        "beanspruchung": beanspruchung,
        "beanspruchung_name": LOAD_CLASSES.get(beanspruchung, {}).get("name_de") if beanspruchung else None,
        "ist_pmb": ist_pmb,
    }


def _ist_polymermodifiziert(bezeichnung: str) -> bool:
    """Prüft ob eine Asphaltbezeichnung auf polymermodifiziertes Bitumen hinweist."""
    keywords = ["PMB", "POLYMER", "MODIFIZIERT", "ELASTOMER",
                "10/40-65", "25/55-55", "45/80-50", "40/100-65"]
    bez_upper = bezeichnung.upper()
    return any(kw in bez_upper for kw in keywords)


def get_suchbegriffe_fuer_bezeichnung(bezeichnung: str) -> Dict[str, List[str]]:
    """
    Generiert relevante Suchbegriffe für EPD-Matching basierend auf einer Asphaltbezeichnung.

    Args:
        bezeichnung: z.B. "AC 16 B S"

    Returns:
        Dict mit kategorisierten Suchbegriffen:
        {
            "typ": [...],
            "schicht": [...],
            "pmb": [...],
            "alle": [...]
        }
    """
    parsed = parse_asphalt_bezeichnung(bezeichnung)
    if not parsed:
        return {"typ": [], "schicht": [], "pmb": [], "alle": []}

    typ_begriffe = ASPHALT_TYPES.get(parsed["typ"], {}).get("suchbegriffe", [])
    schicht_begriffe = LAYER_CODES.get(parsed["schicht"], {}).get("suchbegriffe", []) if parsed["schicht"] else []
    pmb_begriffe = PMB_SUCHBEGRIFFE if parsed["ist_pmb"] else []

    return {
        "typ": typ_begriffe,
        "schicht": schicht_begriffe,
        "pmb": pmb_begriffe,
        "alle": list(set(typ_begriffe + schicht_begriffe + pmb_begriffe))
    }


def get_sortendetails(bezeichnung: str) -> Optional[Dict[str, Any]]:
    """
    Gibt die vollständigen technischen Details einer Asphaltsorte zurück.

    Args:
        bezeichnung: z.B. "AC 16 B S"

    Returns:
        Dict mit allen technischen Anforderungen oder None
    """
    # Normalisieren (Leerzeichen vereinheitlichen)
    bez_normalized = " ".join(bezeichnung.upper().split())

    # Entferne Zusätze wie "SG", "mit Polymermodifiziertem..."
    # Suche nur nach Basis-Bezeichnung
    for sorte in ALLE_ASPHALT_SORTEN.keys():
        if bez_normalized.startswith(sorte):
            return ALLE_ASPHALT_SORTEN[sorte]

    return None


def get_alle_gueltigen_bezeichnungen() -> List[str]:
    """Gibt eine Liste aller gültigen Asphaltbezeichnungen zurück."""
    return list(ALLE_ASPHALT_SORTEN.keys())


# =============================================================================
# PROMPT-GENERIERUNG FÜR GPT
# =============================================================================

def generate_prompt_glossary() -> str:
    """
    Generiert ein kompaktes, strukturiertes Glossar für den GPT-Prompt.
    Basiert auf den Datenstrukturen oben.

    Returns:
        Formatierter String für Einbettung in Prompts
    """
    glossary = """
╔════════════════════════════════════════════════════════════════════╗
║  ASPHALT-BEZEICHNUNGEN NACH TL ASPHALT-STB 07/13                  ║
╚════════════════════════════════════════════════════════════════════╝

📋 AUFBAU: [TYP] [GRÖSSKORN] [SCHICHT] [BEANSPRUCHUNG] [ZUSÄTZE]
   Beispiel: AC 16 B S SG mit PmB 10/40-65A
             │   │  │ │ │
             │   │  │ │ └─ Zusatz (Gesteinsmehl)
             │   │  │ └─── Beanspruchung (S=schwer)
             │   │  └───── Schicht (B=Binder)
             │   └──────── Größtkorn 16mm
             └──────────── Typ (AC=Asphaltbeton)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣  ASPHALT-TYPEN

"""
    # Typen-Tabelle
    for code, info in ASPHALT_TYPES.items():
        begriffe = ", ".join(info["suchbegriffe"][:4])
        glossary += f"  {code:4} = {info['name_de']:25} → EPD-Suche: {begriffe}\n"

    glossary += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2️⃣  SCHICHTCODES (⚠️ KRITISCH FÜR MATCHING!)

"""
    # Schicht-Tabelle
    for code, info in LAYER_CODES.items():
        muss = info.get("epd_muss_enthalten", "")
        glossary += f"  {code:4} = {info['name_de']:25} → EPD-Name MUSS \"{muss}\" enthalten!\n"

    glossary += """
  ⚠️ REGEL: Falscher Schichttyp im EPD-Namen = Confidence < 50%!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3️⃣  BEANSPRUCHUNGSKLASSEN

  S = besondere/schwere Beanspruchung (Autobahnen, Bundesstraßen)
  N = normale Beanspruchung (Landesstraßen, Kreisstraßen)
  L = leichte Beanspruchung (Wohnstraßen, Radwege, Parkplätze)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4️⃣  BINDEMITTEL-HINWEISE

  Polymermodifiziert (PmB) erkennbar an:
  - "Polymermodifiziert", "PmB", "Elastomer" im Text
  - Bindemittel-Codes: 10/40-65, 25/55-55, 45/80-50, 40/100-65

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5️⃣  GÜLTIGE SORTENBEZEICHNUNGEN (36 Sorten)

"""
    # Gruppiert nach Typ
    for typ in ["AC", "SMA", "MA", "PA"]:
        sorten = [s for s in ALLE_ASPHALT_SORTEN.keys() if s.startswith(typ)]
        glossary += f"  {typ}: {', '.join(sorten)}\n"

    glossary += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ AUSSCHLUSS-LISTE (NIEMALS FÜR ASPHALT MATCHEN!)

"""
    # Ausschluss-Begriffe kompakt
    glossary += f"  {', '.join(AUSSCHLUSS_BEGRIFFE[:12])}\n"
    glossary += f"  → Wenn EPD einen dieser Begriffe enthält: Confidence < 30!\n"

    glossary += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📖 MATCHING-BEISPIELE:

  Material: "AC 11 D S" (Deckschicht)
  ├─ ✅ "Asphaltdeckschicht" → 85-100% (D=Deck ✓)
  ├─ ❌ "Asphaltbinder" → <50% (D≠Binder!)
  └─ ❌ "Asphalttragschicht" → <50% (D≠Trag!)

  Material: "AC 16 B S" (Binderschicht)
  ├─ ✅ "Asphaltbinder" → 85-100% (B=Binder ✓)
  ├─ ❌ "Asphaltdeckschicht" → <50% (B≠Deck!)
  └─ ❌ "Asphalttragschicht" → <50% (B≠Trag!)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 CONFIDENCE-BERECHNUNG:

  85-100%: Korrekter SCHICHT-Begriff + TYP + Details
  60-84%:  Korrekter SCHICHT-Begriff + TYP
  40-49%:  TYP vorhanden, aber FALSCHER/KEIN Schicht-Begriff
  30-39%:  Schwacher Asphalt-Bezug
  <30%:    Ausschluss-Begriff → NICHT LISTEN!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return glossary


def generate_material_context(bezeichnung: str) -> str:
    """
    Generiert einen kurzen Kontext-String für eine Material-Bezeichnung.
    Kann dem Prompt hinzugefügt werden um dem LLM zu helfen.

    Args:
        bezeichnung: z.B. "AC 16 B S SG mit PmB"

    Returns:
        Kontext-String, z.B. "AC=Asphaltbeton, B=Binderschicht, EPD muss 'Binder' enthalten, PmB vorhanden"
    """
    parsed = parse_asphalt_bezeichnung(bezeichnung)
    if not parsed:
        return f"Unbekannte Bezeichnung: {bezeichnung}"

    parts = [
        f"{parsed['typ']}={parsed['typ_name']}"
    ]

    if parsed["schicht"]:
        parts.append(f"{parsed['schicht']}={parsed['schicht_name']}")
        if parsed["schicht_epd_muss_enthalten"]:
            parts.append(f"EPD muss '{parsed['schicht_epd_muss_enthalten']}' enthalten")

    if parsed["beanspruchung"]:
        parts.append(f"{parsed['beanspruchung']}={parsed['beanspruchung_name']}")

    if parsed["ist_pmb"]:
        parts.append("PmB vorhanden")

    return ", ".join(parts)


# =============================================================================
# TEST / DEBUG
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("ASPHALT-GLOSSAR TEST")
    print("=" * 70)

    test_bezeichnungen = [
        "AC 11 D S",
        "AC 16 B S SG mit Polymermodifiziertem Bindemittel 10/40-65A",
        "SMA 11 S",
        "MA 8 N",
        "PA 11",
        "AC 32 T N"
    ]

    for bez in test_bezeichnungen:
        print(f"\n{bez}:")
        parsed = parse_asphalt_bezeichnung(bez)
        if parsed:
            print(f"  → {generate_material_context(bez)}")
            suchbegriffe = get_suchbegriffe_fuer_bezeichnung(bez)
            print(f"  → Schicht-Suchbegriffe: {suchbegriffe['schicht'][:3]}")

    print("\n" + "=" * 70)
    print(f"Gesamt: {len(ALLE_ASPHALT_SORTEN)} Asphalt-Sorten definiert")
    print("=" * 70)

    # Test Glossary-Output
    print("\n\nGENERIERTES PROMPT-GLOSSAR (Auszug):")
    print(generate_prompt_glossary()[:2000] + "\n...")