"""Zentrale Konfiguration aus Umgebungsvariablen."""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str) -> bool:
    """
    Konvertiert String zu Boolean (robust).

    True für: "true", "1", "yes", "on" (case-insensitive)
    False für alles andere
    """
    return value.lower().strip() in ("true", "1", "yes", "on")


class AzureConfig:
    """Azure OpenAI Konfiguration."""
    ENDPOINT = os.getenv("ENDPOINT_URL", "").strip()
    API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    DEPLOYMENT = os.getenv("DEPLOYMENT_NAME", "gpt-4o-mini").strip()
    API_VERSION = "2024-08-01-preview"
    TIMEOUT = 240.0
    MAX_RETRIES = 3


class APIConfig:
    """Online EPD API Konfiguration."""
    BASE_URL = os.getenv("ONLINE_EPD_API_BASE_URL", "").strip().rstrip("/")
    USERNAME = os.getenv("ONLINE_EPD_API_USERNAME", "").strip()
    PASSWORD = (
        os.getenv("ONLINE_EPD_API_PASSWORD") or
        os.getenv("ONLINE_EPD_API_PASSWORT") or ""
    ).strip()
    GROUP_VALUE = os.getenv("ONLINE_EPD_GROUP_VALUE", "").strip()


class MatchingConfig:
    """EPD Matching Konfiguration."""

    # NEU: Matching-Modus umschalten
    USE_DETAIL_MATCHING = _parse_bool(os.getenv("EPD_USE_DETAIL_MATCHING", "false"))

    # Spalten (nur relevant wenn USE_DETAIL_MATCHING=true)
    COLUMNS: List[str] = [
        c.strip() for c in
        os.getenv("EPD_MATCHING_COLUMNS", "name,technischeBeschreibung,anmerkungen").split(",")
    ]

    FILTER_LABELS: List[str] = [
        s.strip() for s in
        os.getenv("EPD_FILTER_LABELS", "").split(",") if s.strip()
    ]

    # Limitiert die Anzahl EPDs im Prompt
    MAX_EPD_IN_PROMPT = int(os.getenv("PROMPT_MAX_EPD", "1000"))

    USE_FILTER_LABELS = _parse_bool(os.getenv("EPD_USE_FILTER_LABELS", "false"))

    # Parallel-Workers für Detail-Loading (nur relevant wenn USE_DETAIL_MATCHING=true)
    PARALLEL_WORKERS = int(os.getenv("EPD_PARALLEL_WORKERS", "10"))

# Debug-Output (ganz unten in der Datei)
print(f"\n{'=' * 70}")
print("CONFIG DEBUG")
print(f"{'=' * 70}")
print(f"EPD_USE_DETAIL_MATCHING (env): '{os.getenv('EPD_USE_DETAIL_MATCHING', 'NOT SET')}'")
print(f"USE_DETAIL_MATCHING (parsed): {MatchingConfig.USE_DETAIL_MATCHING}")
print(f"PROMPT_MAX_EPD: {MatchingConfig.MAX_EPD_IN_PROMPT}")
print(f"PARALLEL_WORKERS: {MatchingConfig.PARALLEL_WORKERS}")
print(f"{'=' * 70}\n")