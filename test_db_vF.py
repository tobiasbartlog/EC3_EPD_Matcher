"""
EPD Database Explorer
Zeigt alle verfügbaren Spalten und Beispiel-Einträge aus der EPD-Datenbank.
"""
import os
import json
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Konfiguration aus .env
API_BASE = os.getenv("ONLINE_EPD_API_BASE_URL", "").strip().rstrip("/")
API_USERNAME = os.getenv("ONLINE_EPD_API_USERNAME", "").strip()
API_PASSWORD = (
    os.getenv("ONLINE_EPD_API_PASSWORD") or
    os.getenv("ONLINE_EPD_API_PASSWORT") or ""
).strip()


def get_auth_token() -> str:
    """Holt Authentication Token von der API."""
    url = f"{API_BASE}/api/Auth/getToken"
    body = {"username": API_USERNAME, "passwort": API_PASSWORD}

    print(f"🔐 Hole Auth-Token von: {url}")
    response = requests.post(url, json=body, timeout=20)
    response.raise_for_status()

    # Versuche JSON zu parsen
    try:
        payload = response.json()
        # Wenn es ein Dict ist, suche nach Token-Feldern
        if isinstance(payload, dict):
            token = (
                payload.get("token") or
                payload.get("access_token") or
                payload.get("jwt")
            )
        else:
            # Wenn JSON aber kein Dict (z.B. String in JSON), nehme direkt
            token = str(payload).strip()
    except (ValueError, json.JSONDecodeError):
        # Kein JSON - nehme Response-Text direkt
        token = response.text.strip()

    if not token:
        raise RuntimeError("❌ Kein Token in Auth-Antwort gefunden")

    print("✅ Token erfolgreich erhalten\n")
    return token


def get_epd_data(token: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Holt EPD-Daten von der API.

    Args:
        token: Auth-Token
        limit: Anzahl der zu holenden Einträge

    Returns:
        Liste von EPD-Einträgen
    """
    url = f"{API_BASE}/api/Datasets"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    print(f"📊 Hole {limit} EPD-Einträge von: {url}")
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()

    data = response.json()

    # Verschiedene Response-Formate unterstützen
    if isinstance(data, list):
        items = data[:limit]
    elif isinstance(data, dict) and "items" in data:
        items = data["items"][:limit] if isinstance(data["items"], list) else []
    else:
        items = []

    print(f"✅ {len(items)} Einträge erhalten (Liste)\n")
    return items


def get_epd_detail(token: str, epd_id: int) -> Optional[Dict[str, Any]]:
    """
    Holt detaillierte Informationen zu einem einzelnen EPD-Eintrag.

    Args:
        token: Auth-Token
        epd_id: ID des EPD-Eintrags

    Returns:
        Detaillierter EPD-Eintrag oder None
    """
    url = f"{API_BASE}/api/Datasets/{epd_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    try:
        print(f"🔍 Hole Details für EPD-ID {epd_id}...")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        detail = response.json()

        # API könnte Liste oder Objekt zurückgeben
        if isinstance(detail, list):
            if detail:
                print(f"✅ Detail-Daten erhalten (Liste mit {len(detail)} Einträgen)\n")
                return detail[0]  # Nehme ersten Eintrag
            else:
                print(f"⚠️  Leere Liste zurückgegeben\n")
                return None
        elif isinstance(detail, dict):
            print(f"✅ Detail-Daten erhalten (Objekt)\n")
            return detail
        else:
            print(f"⚠️  Unerwartetes Format: {type(detail)}\n")
            return None

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"⚠️  Detail-Endpoint nicht verfügbar (404)\n")
        else:
            print(f"⚠️  Detail-Endpoint Fehler: {e}\n")
        return None
    except Exception as e:
        print(f"⚠️  Fehler beim Laden der Details: {e}\n")
        return None


def analyze_fields(epds: List[Dict[str, Any]]) -> None:
    """
    Analysiert und zeigt alle verfügbaren Felder.

    Args:
        epds: Liste von EPD-Einträgen
    """
    if not epds:
        print("❌ Keine EPD-Einträge zum Analysieren")
        return

    # Sammle alle Feldnamen aus allen Einträgen
    all_fields = set()
    for epd in epds:
        all_fields.update(epd.keys())

    print("="*80)
    print(f"VERFÜGBARE FELDER ({len(all_fields)} gesamt)")
    print("="*80)

    # Sortiere Felder alphabetisch
    sorted_fields = sorted(all_fields)

    for i, field in enumerate(sorted_fields, 1):
        print(f"{i:2d}. {field}")

    print("\n")


def show_example_entry(epd: Dict[str, Any], entry_number: int = 1) -> None:
    """
    Zeigt einen vollständigen EPD-Eintrag mit allen Feldern.

    Args:
        epd: EPD-Eintrag Dictionary
        entry_number: Nummer des Eintrags (für Überschrift)
    """
    print("="*80)
    print(f"BEISPIEL-EINTRAG #{entry_number}")
    print("="*80)

    # Sortiere Felder alphabetisch für bessere Übersicht
    sorted_fields = sorted(epd.keys())

    for field in sorted_fields:
        value = epd[field]

        # Formatierung je nach Typ
        if value is None:
            display_value = "NULL"
        elif isinstance(value, str):
            # Lange Strings abschneiden
            if len(value) > 200:
                display_value = f'"{value[:200]}..." (gekürzt, Original: {len(value)} Zeichen)'
            else:
                display_value = f'"{value}"'
        elif isinstance(value, (list, dict)):
            display_value = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            display_value = str(value)

        print(f"\n{field}:")
        print(f"  {display_value}")

    print("\n")


def show_field_statistics(epds: List[Dict[str, Any]]) -> None:
    """
    Zeigt Statistiken über Feldverfügbarkeit.

    Args:
        epds: Liste von EPD-Einträgen
    """
    if not epds:
        return

    # Sammle alle Felder und zähle, wie oft sie befüllt sind
    field_stats = {}

    for epd in epds:
        for field, value in epd.items():
            if field not in field_stats:
                field_stats[field] = {"total": 0, "filled": 0, "empty": 0}

            field_stats[field]["total"] += 1

            if value is None or value == "" or value == []:
                field_stats[field]["empty"] += 1
            else:
                field_stats[field]["filled"] += 1

    print("="*80)
    print("FELD-STATISTIKEN (Verfügbarkeit)")
    print("="*80)
    print(f"{'Feldname':<40} {'Befüllt':<10} {'Leer':<10} {'%':<10}")
    print("-"*80)

    # Sortiere nach Feldname
    for field in sorted(field_stats.keys()):
        stats = field_stats[field]
        percentage = (stats["filled"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"{field:<40} {stats['filled']:<10} {stats['empty']:<10} {percentage:>6.1f}%")

    print("\n")


def export_to_file(data: Any, filename: str = "epd_structure.json") -> None:
    """
    Exportiert die EPD-Struktur in eine JSON-Datei.

    Args:
        data: Zu exportierende Daten
        filename: Dateiname für Export
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Daten exportiert nach: {filename}\n")
    except Exception as e:
        print(f"❌ Export fehlgeschlagen: {e}\n")


def main():
    """Hauptfunktion."""
    print("\n" + "="*80)
    print("EPD DATABASE EXPLORER")
    print("="*80 + "\n")

    # Validierung
    if not all([API_BASE, API_USERNAME, API_PASSWORD]):
        print("❌ Fehler: API-Konfiguration unvollständig!")
        print("   Bitte setze in .env:")
        print("   - ONLINE_EPD_API_BASE_URL")
        print("   - ONLINE_EPD_API_USERNAME")
        print("   - ONLINE_EPD_API_PASSWORD (oder ONLINE_EPD_API_PASSWORT)")
        return

    print(f"🌐 API-Basis-URL: {API_BASE}")
    print(f"👤 Username: {API_USERNAME}\n")

    try:
        # 1. Token holen
        token = get_auth_token()

        # 2. EPD-Listen-Daten holen
        epds_list = get_epd_data(token, limit=10)

        if not epds_list:
            print("❌ Keine EPD-Einträge gefunden!")
            return

        print("="*80)
        print("LISTE: VERFÜGBARE FELDER")
        print("="*80)
        analyze_fields(epds_list)

        # 3. Versuche Detail-Daten für ersten Eintrag zu holen
        first_id = epds_list[0].get("id")
        epd_detail = None

        if first_id:
            print("="*80)
            print("VERSUCHE DETAIL-DATEN ZU LADEN")
            print("="*80 + "\n")
            epd_detail = get_epd_detail(token, first_id)

            if epd_detail:
                print("="*80)
                print("DETAIL: VERFÜGBARE FELDER")
                print("="*80)
                analyze_fields([epd_detail])

        # 4. Zeige Beispiel-Einträge
        print("="*80)
        print("LISTEN-EINTRAG (Übersicht)")
        print("="*80)
        show_example_entry(epds_list[0], entry_number=1)

        if epd_detail:
            print("="*80)
            print("DETAIL-EINTRAG (Vollständig)")
            print("="*80)
            show_example_entry(epd_detail, entry_number=1)

        # 5. Statistiken nur für Listen-Daten
        show_field_statistics(epds_list)

        # 6. Export
        export_data = {
            "list_data": epds_list,
            "detail_data": epd_detail if epd_detail else None
        }
        export_to_file(export_data, "epd_structure.json")

        # 7. Zusammenfassung
        print("="*80)
        print("ZUSAMMENFASSUNG")
        print("="*80)
        print(f"✓ {len(epds_list)} Listen-Einträge analysiert")
        if epd_detail:
            print(f"✓ 1 Detail-Eintrag analysiert")

        # Zeige wichtige Felder
        print("\n📌 In Listen-Daten verfügbar:")
        list_fields = set()
        for epd in epds_list:
            list_fields.update(epd.keys())
        for field in sorted(list_fields):
            print(f"   - {field}")

        if epd_detail:
            print("\n📌 In Detail-Daten zusätzlich verfügbar:")
            detail_fields = set(epd_detail.keys()) - list_fields
            if detail_fields:
                for field in sorted(detail_fields):
                    print(f"   - {field}")
            else:
                print("   (keine zusätzlichen Felder)")

        print("\n💡 EMPFEHLUNG für EPD_MATCHING_COLUMNS:")
        available_for_matching = [f for f in sorted(list_fields)
                                 if f in ["name", "klassifizierung", "beschreibung",
                                         "general_comment_de", "tech_desc_de"]]
        if available_for_matching:
            print(f"   EPD_MATCHING_COLUMNS={','.join(available_for_matching)}")
        else:
            print(f"   EPD_MATCHING_COLUMNS=name")

        print("\n" + "="*80 + "\n")

    except requests.exceptions.RequestException as e:
        print(f"❌ API-Fehler: {e}")
    except Exception as e:
        print(f"❌ Fehler: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()