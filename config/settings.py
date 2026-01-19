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

    # Matching-Modus
    USE_DETAIL_MATCHING = _parse_bool(os.getenv("EPD_USE_DETAIL_MATCHING", "false"))

    # Spalten für Detail-Matching
    COLUMNS: List[str] = [
        c.strip() for c in
        os.getenv("EPD_MATCHING_COLUMNS", "name,technischeBeschreibung,anmerkungen").split(",")
    ]

    # Limitiert die Anzahl EPDs im Prompt
    MAX_EPD_IN_PROMPT = int(os.getenv("PROMPT_MAX_EPD", "200"))

    # Parallel-Workers für Detail-Loading
    PARALLEL_WORKERS = int(os.getenv("EPD_PARALLEL_WORKERS", "10"))

    # Legacy Label-Filter (wird durch Glossar ersetzt)
    USE_FILTER_LABELS = _parse_bool(os.getenv("EPD_USE_FILTER_LABELS", "false"))
    FILTER_LABELS: List[str] = [
        s.strip() for s in
        os.getenv("EPD_FILTER_LABELS", "").split(",") if s.strip()
    ]


class GlossarConfig:
    """Asphalt-Glossar Konfiguration (NEU)."""

    # Glossar aktivieren (intelligentes Parsing + Prompt-Verbesserung)
    USE_GLOSSAR = _parse_bool(os.getenv("EPD_USE_GLOSSAR", "true"))

    # Vorfilterung aktivieren (reduziert EPDs vor GPT-Call)
    USE_GLOSSAR_FILTER = _parse_bool(os.getenv("EPD_USE_GLOSSAR_FILTER", "true"))

    # Maximale EPDs pro Material bei Vorfilterung
    FILTER_MAX_PER_MATERIAL = int(os.getenv("EPD_GLOSSAR_FILTER_MAX", "100"))

    # Confidence-Nachvalidierung aktivieren
    USE_CONFIDENCE_VALIDATION = _parse_bool(os.getenv("EPD_USE_CONFIDENCE_VALIDATION", "true"))

    # Debug-Output
    DEBUG = _parse_bool(os.getenv("EPD_GLOSSAR_DEBUG", "false"))


# =============================================================================
# DEBUG OUTPUT
# =============================================================================

def print_config_debug():
    """Gibt Konfiguration zur Laufzeit aus."""
    print(f"\n{'=' * 70}")
    print("CONFIG DEBUG")
    print(f"{'=' * 70}")
    print(f"Azure Deployment: {AzureConfig.DEPLOYMENT}")
    print(f"EPD API: {APIConfig.BASE_URL}")
    print()
    print("Matching:")
    print(f"  USE_DETAIL_MATCHING: {MatchingConfig.USE_DETAIL_MATCHING}")
    print(f"  MAX_EPD_IN_PROMPT: {MatchingConfig.MAX_EPD_IN_PROMPT}")
    print(f"  PARALLEL_WORKERS: {MatchingConfig.PARALLEL_WORKERS}")
    print()
    print("Glossar (NEU):")
    print(f"  USE_GLOSSAR: {GlossarConfig.USE_GLOSSAR}")
    print(f"  USE_GLOSSAR_FILTER: {GlossarConfig.USE_GLOSSAR_FILTER}")
    print(f"  FILTER_MAX_PER_MATERIAL: {GlossarConfig.FILTER_MAX_PER_MATERIAL}")
    print(f"  USE_CONFIDENCE_VALIDATION: {GlossarConfig.USE_CONFIDENCE_VALIDATION}")
    print(f"  DEBUG: {GlossarConfig.DEBUG}")
    print()
    print("Legacy Filter:")
    print(f"  USE_FILTER_LABELS: {MatchingConfig.USE_FILTER_LABELS}")
    if MatchingConfig.USE_FILTER_LABELS:
        print(f"  FILTER_LABELS: {MatchingConfig.FILTER_LABELS[:5]}...")
    print(f"{'=' * 70}\n")


# Automatischer Debug-Output beim Import
print_config_debug()