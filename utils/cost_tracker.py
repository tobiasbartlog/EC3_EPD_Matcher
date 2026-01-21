"""
Token- und Kostenberechnung für Azure OpenAI API-Calls.

Trackt:
- Input/Output Tokens pro Request
- Kumulative Kosten pro Session
- Kosten pro Modell
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


# =============================================================================
# PREISE PRO 1M TOKENS (Stand: Januar 2026)
# =============================================================================
# Quelle: https://platform.openai.com/docs/pricing (Standard Tier)
# Format: {"model_pattern": {"input": preis_pro_1M, "output": preis_pro_1M}}

MODEL_PRICES: Dict[str, Dict[str, float]] = {
    # =========================================================================
    # DEINE AZURE DEPLOYMENTS (Globaler Standard)
    # =========================================================================
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},      # Deployment: gpt-4o-mini
    "gpt-5-chat": {"input": 1.25, "output": 10.00},     # Deployment: gpt-5-chat
    "gpt-5-nano": {"input": 0.05, "output": 0.40},      # Deployment: gpt-5-nano
    "gpt-5.2-chat": {"input": 1.75, "output": 14.00},   # Deployment: gpt-5.2-chat

    # =========================================================================
    # GPT-5 Familie (vollständig)
    # =========================================================================
    "gpt-5.2": {"input": 1.75, "output": 14.00},
    "gpt-5.1": {"input": 1.25, "output": 10.00},
    "gpt-5": {"input": 1.25, "output": 10.00},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
    "gpt-5-pro": {"input": 15.00, "output": 120.00},
    "gpt-5.2-pro": {"input": 21.00, "output": 168.00},

    # GPT-5 Codex
    "gpt-5.2-codex": {"input": 1.75, "output": 14.00},
    "gpt-5.1-codex": {"input": 1.25, "output": 10.00},
    "gpt-5-codex": {"input": 1.25, "output": 10.00},
    "gpt-5.1-codex-mini": {"input": 0.25, "output": 2.00},

    # =========================================================================
    # GPT-4.1 Familie
    # =========================================================================
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},

    # =========================================================================
    # GPT-4o Familie
    # =========================================================================
    "gpt-4o": {"input": 2.50, "output": 10.00},

    # =========================================================================
    # O-Serie Reasoning Models
    # =========================================================================
    "o1": {"input": 15.00, "output": 60.00},
    "o1-pro": {"input": 150.00, "output": 600.00},
    "o1-mini": {"input": 1.10, "output": 4.40},
    "o3": {"input": 2.00, "output": 8.00},
    "o3-pro": {"input": 20.00, "output": 80.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "o4-mini": {"input": 1.10, "output": 4.40},

    # =========================================================================
    # Embeddings
    # =========================================================================
    "text-embedding-3-small": {"input": 0.02, "output": 0.00},
    "text-embedding-3-large": {"input": 0.13, "output": 0.00},

    # =========================================================================
    # Legacy
    # =========================================================================
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},

    # Fallback (gpt-4o-mini als günstiger Standard)
    "default": {"input": 0.15, "output": 0.60},
}


@dataclass
class APICallRecord:
    """Einzelner API-Call Record."""
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    context: str = ""  # z.B. "batch_matching" oder "single_matching"


@dataclass
class CostTracker:
    """Trackt Token-Nutzung und Kosten über eine Session."""

    calls: list = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    session_start: datetime = field(default_factory=datetime.now)

    def record_call(
        self,
        model: str,
        usage: Dict[str, Any],
        context: str = ""
    ) -> APICallRecord:
        """
        Zeichnet einen API-Call auf.

        Args:
            model: Modell-Name (z.B. "gpt-4o-mini")
            usage: Usage-Dict aus der API-Response
            context: Optionaler Kontext (z.B. "batch_matching")

        Returns:
            APICallRecord mit Kosten-Details
        """
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

        # Kosten berechnen
        prices = self._get_prices(model)
        input_cost = (input_tokens / 1_000_000) * prices["input"]
        output_cost = (output_tokens / 1_000_000) * prices["output"]
        total_cost = input_cost + output_cost

        # Record erstellen
        record = APICallRecord(
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            context=context
        )

        # Kumulative Werte aktualisieren
        self.calls.append(record)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += total_cost

        return record

    def _get_prices(self, model: str) -> Dict[str, float]:
        """Ermittelt Preise für ein Modell."""
        model_lower = model.lower()

        # Exakter Match
        if model_lower in MODEL_PRICES:
            return MODEL_PRICES[model_lower]

        # Partial Match (z.B. "gpt-4o-mini-2024" -> "gpt-4o-mini")
        for pattern, prices in MODEL_PRICES.items():
            if pattern in model_lower:
                return prices

        return MODEL_PRICES["default"]

    def get_summary(self) -> Dict[str, Any]:
        """Gibt Zusammenfassung der Session zurück."""
        return {
            "session_start": self.session_start.isoformat(),
            "total_calls": len(self.calls),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "total_cost_eur": round(self.total_cost * 0.92, 6),  # Ungefährer Wechselkurs
        }

    def print_call_summary(self, record: APICallRecord) -> None:
        """Gibt kompakte Zusammenfassung eines Calls aus."""
        print(f"  💰 Tokens: {record.input_tokens:,} in + {record.output_tokens:,} out = {record.total_tokens:,}")
        print(f"  💵 Kosten: ${record.total_cost:.6f} ({record.model})")

    def print_session_summary(self) -> None:
        """Gibt Zusammenfassung der gesamten Session aus."""
        summary = self.get_summary()

        print(f"\n{'='*60}")
        print("💰 KOSTEN-ZUSAMMENFASSUNG")
        print(f"{'='*60}")
        print(f"  API-Calls:      {summary['total_calls']}")
        print(f"  Input Tokens:   {summary['total_input_tokens']:,}")
        print(f"  Output Tokens:  {summary['total_output_tokens']:,}")
        print(f"  Gesamt Tokens:  {summary['total_tokens']:,}")
        print(f"  {'-'*40}")
        print(f"  Kosten (USD):   ${summary['total_cost_usd']:.4f}")
        print(f"  Kosten (EUR):   ~€{summary['total_cost_eur']:.4f}")
        print(f"{'='*60}\n")

    def get_cost_per_model(self) -> Dict[str, Dict[str, Any]]:
        """Gruppiert Kosten nach Modell."""
        by_model: Dict[str, Dict[str, Any]] = {}

        for call in self.calls:
            if call.model not in by_model:
                by_model[call.model] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_cost": 0.0
                }

            by_model[call.model]["calls"] += 1
            by_model[call.model]["input_tokens"] += call.input_tokens
            by_model[call.model]["output_tokens"] += call.output_tokens
            by_model[call.model]["total_cost"] += call.total_cost

        return by_model


# =============================================================================
# GLOBALE INSTANZ
# =============================================================================

_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """Gibt globale CostTracker-Instanz zurück (Singleton)."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker


def reset_tracker() -> None:
    """Setzt den globalen Tracker zurück."""
    global _tracker
    _tracker = CostTracker()


def record_usage(model: str, usage: Dict[str, Any], context: str = "") -> APICallRecord:
    """Shortcut zum Aufzeichnen eines API-Calls."""
    return get_tracker().record_call(model, usage, context)


def print_summary() -> None:
    """Shortcut zum Ausgeben der Session-Zusammenfassung."""
    get_tracker().print_session_summary()


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("COST TRACKER TEST - Deine Azure Deployments")
    print("=" * 60)

    tracker = CostTracker()

    # Teste alle 4 Azure Deployments
    deployments = [
        ("gpt-4o-mini", 5000, 1000),      # günstigstes
        ("gpt-5-nano", 5000, 1000),        # sehr günstig
        ("gpt-5-chat", 5000, 1000),        # mittel
        ("gpt-5.2-chat", 5000, 1000),      # neuestes
    ]

    for model, inp, out in deployments:
        record = tracker.record_call(
            model=model,
            usage={"prompt_tokens": inp, "completion_tokens": out},
            context="test"
        )
        print(f"\n📌 {model}:")
        tracker.print_call_summary(record)

    # Zusammenfassung
    tracker.print_session_summary()

    # Kosten pro Modell
    print("Kosten pro Modell (5K input + 1K output):")
    print("-" * 45)
    for model, stats in tracker.get_cost_per_model().items():
        print(f"  {model:20} ${stats['total_cost']:.6f}")