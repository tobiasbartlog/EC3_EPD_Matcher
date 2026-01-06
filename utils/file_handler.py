"""Datei-Handler für JSON-Operationen."""
import json
import sys
from pathlib import Path
from typing import Dict, Any


def load_json(path: Path) -> Dict[str, Any]:
    """
    Lädt eine JSON-Datei.

    Args:
        path: Pfad zur JSON-Datei

    Returns:
        Geladene JSON-Daten als Dictionary

    Raises:
        SystemExit: Bei Datei-nicht-gefunden oder Parse-Fehler
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Fehler: Datei nicht gefunden: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Fehler: Ungültige JSON-Datei: {e}")
        sys.exit(1)


def save_json(data: Dict[str, Any], path: Path) -> None:
    """
    Speichert Daten als JSON-Datei.

    Args:
        data: Zu speichernde Daten
        path: Ziel-Pfad für die JSON-Datei

    Raises:
        SystemExit: Bei Speicher-Fehler
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✓ Output erfolgreich gespeichert: {path}")
    except Exception as e:
        print(f"Fehler beim Speichern: {e}")
        sys.exit(1)