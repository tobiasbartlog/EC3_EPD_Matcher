"""Zentrale Konfiguration aus Umgebungsvariablen.

Struktur orientiert sich an den 5 Stages aus dem Paper:
  Stage 1: Context Extraction
  Stage 2: Material Code Parsing
  Stage 3: EPD Pre-filtering
  Stage 4: Semantic Matching (LLM)
  Stage 5: Result Aggregation / Confidence Validation
"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str) -> bool:
    """Konvertiert String zu Boolean (robust)."""
    return value.lower().strip() in ("true", "1", "yes", "on")


def _parse_int(value: str, default: int) -> int:
    """Konvertiert String zu Integer mit Default."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# =============================================================================
# AZURE OPENAI (Stage 4)
# =============================================================================

class AzureConfig:
    """Azure OpenAI Konfiguration."""
    ENDPOINT = os.getenv("ENDPOINT_URL", "").strip()
    API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    DEPLOYMENT = os.getenv("DEPLOYMENT_NAME", "gpt-4o-mini").strip()
    API_VERSION = os.getenv("AZURE_API_VERSION", "2024-08-01-preview").strip()
    TIMEOUT = float(os.getenv("AZURE_TIMEOUT", "240.0"))
    MAX_RETRIES = _parse_int(os.getenv("AZURE_MAX_RETRIES", "3"), 3)


# =============================================================================
# EPD DATABASE API
# =============================================================================

class APIConfig:
    """Online EPD API Konfiguration."""
    BASE_URL = os.getenv("ONLINE_EPD_API_BASE_URL", "").strip().rstrip("/")
    USERNAME = os.getenv("ONLINE_EPD_API_USERNAME", "").strip()
    PASSWORD = (
        os.getenv("ONLINE_EPD_API_PASSWORD") or
        os.getenv("ONLINE_EPD_API_PASSWORT") or ""
    ).strip()
    GROUP_VALUE = os.getenv("ONLINE_EPD_GROUP_VALUE", "").strip()


# =============================================================================
# STAGE 1: CONTEXT EXTRACTION
# =============================================================================

class ContextConfig:
    """Stage 1: Kontext-Extraktion aus Input-JSON."""
    # Priorität der Schicht-Information (NAME-Feld vs. MATERIAL-Feld)
    PREFER_NAME_FIELD = _parse_bool(os.getenv("EPD_PREFER_NAME_FIELD", "true"))

    # Volumen für LCA-Berechnung extrahieren
    EXTRACT_VOLUME = _parse_bool(os.getenv("EPD_EXTRACT_VOLUME", "true"))


# =============================================================================
# STAGE 2: MATERIAL CODE PARSING (Glossar)
# =============================================================================

class GlossarConfig:
    """Stage 2: Asphalt-Glossar / TL Asphalt-StB Parsing."""

    # Glossar aktivieren (intelligentes Parsing)
    USE_GLOSSAR = _parse_bool(os.getenv("EPD_USE_GLOSSAR", "true"))

    # Debug-Output für Parsing-Ergebnisse
    DEBUG = _parse_bool(os.getenv("EPD_GLOSSAR_DEBUG", "false"))


# =============================================================================
# STAGE 3: EPD PRE-FILTERING
# =============================================================================

class FilterConfig:
    """Stage 3: EPD-Vorfilterung."""

    # Glossar-basierte Vorfilterung aktivieren
    USE_GLOSSAR_FILTER = _parse_bool(os.getenv("EPD_USE_GLOSSAR_FILTER", "true"))

    # Maximale EPDs pro Material nach Filterung
    FILTER_MAX_PER_MATERIAL = _parse_int(
        os.getenv("EPD_GLOSSAR_FILTER_MAX", "100"), 100
    )

    # Legacy: Einfacher Label-Filter
    USE_FILTER_LABELS = _parse_bool(os.getenv("EPD_USE_FILTER_LABELS", "false"))
    FILTER_LABELS: List[str] = [
        s.strip() for s in
        os.getenv("EPD_FILTER_LABELS", "").split(",") if s.strip()
    ]


# =============================================================================
# STAGE 4: SEMANTIC MATCHING (LLM)
# =============================================================================

class MatchingConfig:
    """Stage 4: LLM-basiertes Matching."""

    # Maximale EPDs im Prompt (Token-Limit!)
    MAX_EPD_IN_PROMPT = _parse_int(os.getenv("PROMPT_MAX_EPD", "200"), 200)

    # Detail-Matching: technischeBeschreibung etc. laden
    USE_DETAIL_MATCHING = _parse_bool(os.getenv("EPD_USE_DETAIL_MATCHING", "false"))

    # Spalten für Detail-Matching
    COLUMNS: List[str] = [
        c.strip() for c in
        os.getenv("EPD_MATCHING_COLUMNS", "name,technischeBeschreibung,anmerkungen").split(",")
    ]

    # Parallele API-Calls für Detail-Loading
    PARALLEL_WORKERS = _parse_int(os.getenv("EPD_PARALLEL_WORKERS", "10"), 10)

    # Batch-Modus (alle Schichten in einem Call)
    USE_BATCH_MODE = _parse_bool(os.getenv("EPD_USE_BATCH_MODE", "true"))

    # Maximale Ergebnisse pro Material
    MAX_RESULTS = _parse_int(os.getenv("EPD_MAX_RESULTS", "10"), 10)


# =============================================================================
# STAGE 5: RESULT AGGREGATION / CONFIDENCE VALIDATION
# =============================================================================

class ValidationConfig:
    """Stage 5: Confidence-Nachvalidierung."""

    # Nachvalidierung aktivieren
    USE_CONFIDENCE_VALIDATION = _parse_bool(
        os.getenv("EPD_USE_CONFIDENCE_VALIDATION", "true")
    )

    # Minimale Confidence für Ergebnisse (darunter wird gefiltert)
    MIN_CONFIDENCE = _parse_int(os.getenv("EPD_MIN_CONFIDENCE", "25"), 25)

    # Maximale Confidence für Ausschluss-Begriffe
    MAX_CONFIDENCE_EXCLUDED = _parse_int(
        os.getenv("EPD_MAX_CONFIDENCE_EXCLUDED", "20"), 20
    )


# =============================================================================
# BACKWARDS COMPATIBILITY (Legacy-Namen)
# =============================================================================
# Diese Klasse existiert für Kompatibilität mit bestehendem Code

class _LegacyMatchingConfig:
    """Legacy-Wrapper für alte Variablennamen."""

    @property
    def USE_DETAIL_MATCHING(self):
        return MatchingConfig.USE_DETAIL_MATCHING

    @property
    def COLUMNS(self):
        return MatchingConfig.COLUMNS

    @property
    def MAX_EPD_IN_PROMPT(self):
        return MatchingConfig.MAX_EPD_IN_PROMPT

    @property
    def PARALLEL_WORKERS(self):
        return MatchingConfig.PARALLEL_WORKERS

    @property
    def USE_FILTER_LABELS(self):
        return FilterConfig.USE_FILTER_LABELS

    @property
    def FILTER_LABELS(self):
        return FilterConfig.FILTER_LABELS


# =============================================================================
# DEBUG OUTPUT
# =============================================================================

def print_config_debug():
    """Gibt Konfiguration zur Laufzeit aus."""
    print(f"\n{'=' * 70}")
    print("EPD MATCHER - KONFIGURATION")
    print(f"{'=' * 70}")

    print("\n[Azure OpenAI - Stage 4]")
    print(f"  Endpoint:   {AzureConfig.ENDPOINT[:50]}..." if len(AzureConfig.ENDPOINT) > 50 else f"  Endpoint:   {AzureConfig.ENDPOINT}")
    print(f"  Deployment: {AzureConfig.DEPLOYMENT}")
    print(f"  Timeout:    {AzureConfig.TIMEOUT}s")

    print("\n[EPD API]")
    print(f"  Base URL:   {APIConfig.BASE_URL}")
    print(f"  Username:   {APIConfig.USERNAME}")

    print("\n[Stage 1: Context Extraction]")
    print(f"  PREFER_NAME_FIELD:  {ContextConfig.PREFER_NAME_FIELD}")
    print(f"  EXTRACT_VOLUME:     {ContextConfig.EXTRACT_VOLUME}")

    print("\n[Stage 2: Material Code Parsing]")
    print(f"  USE_GLOSSAR:        {GlossarConfig.USE_GLOSSAR}")
    print(f"  DEBUG:              {GlossarConfig.DEBUG}")

    print("\n[Stage 3: EPD Pre-filtering]")
    print(f"  USE_GLOSSAR_FILTER: {FilterConfig.USE_GLOSSAR_FILTER}")
    print(f"  FILTER_MAX:         {FilterConfig.FILTER_MAX_PER_MATERIAL}")
    print(f"  USE_FILTER_LABELS:  {FilterConfig.USE_FILTER_LABELS} (legacy)")

    print("\n[Stage 4: Semantic Matching]")
    print(f"  MAX_EPD_IN_PROMPT:  {MatchingConfig.MAX_EPD_IN_PROMPT}")
    print(f"  USE_DETAIL_MATCHING:{MatchingConfig.USE_DETAIL_MATCHING}")
    print(f"  USE_BATCH_MODE:     {MatchingConfig.USE_BATCH_MODE}")
    print(f"  PARALLEL_WORKERS:   {MatchingConfig.PARALLEL_WORKERS}")

    print("\n[Stage 5: Confidence Validation]")
    print(f"  USE_VALIDATION:     {ValidationConfig.USE_CONFIDENCE_VALIDATION}")
    print(f"  MIN_CONFIDENCE:     {ValidationConfig.MIN_CONFIDENCE}")

    print(f"\n{'=' * 70}\n")


def get_stage_status() -> dict:
    """Gibt Status aller Stages als Dictionary zurück."""
    return {
        "stage_1_context": True,  # Immer aktiv
        "stage_2_parsing": GlossarConfig.USE_GLOSSAR,
        "stage_3_filtering": FilterConfig.USE_GLOSSAR_FILTER,
        "stage_4_llm": True,  # Immer aktiv (Kernfunktion)
        "stage_5_validation": ValidationConfig.USE_CONFIDENCE_VALIDATION,
    }


# Automatischer Debug-Output beim Import
print_config_debug()