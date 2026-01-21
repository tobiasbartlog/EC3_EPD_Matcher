#!/usr/bin/env python3
"""
Benchmark-Skript für Azure OpenAI Modell-Vergleich.

Vergleicht alle 4 Azure Deployments:
- gpt-4o-mini
- gpt-5-nano
- gpt-5-chat
- gpt-5.2-chat

Misst: Tokens, Kosten, Zeit, Ergebnisse pro Schicht
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, field, asdict

# UTF-8 für Konsole
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# =============================================================================
# KONFIGURATION
# =============================================================================

MODELS = [
    "gpt-4o-mini",
    "gpt-5-nano",
    "gpt-5-chat",
    "gpt-5.2-chat",
]

# Preise pro 1M Tokens (Standard Tier, Januar 2026)
MODEL_PRICES = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
    "gpt-5-chat": {"input": 1.25, "output": 10.00},
    "gpt-5.2-chat": {"input": 1.75, "output": 14.00},
}


# =============================================================================
# DATENKLASSEN
# =============================================================================

@dataclass
class SchichtResult:
    """Ergebnis einer einzelnen Schicht."""
    name: str
    material: str
    match_count: int
    top_match_id: str = ""
    top_match_name: str = ""
    top_confidence: int = 0
    all_ids: List[str] = field(default_factory=list)


@dataclass
class ModelRun:
    """Ergebnis eines Modell-Durchlaufs."""
    model: str
    start_time: str
    duration_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    cost_eur: float
    schichten: List[SchichtResult] = field(default_factory=list)
    error: str = ""


@dataclass
class BenchmarkResult:
    """Gesamt-Benchmark-Ergebnis."""
    timestamp: str
    input_file: str
    total_schichten: int
    runs: List[ModelRun] = field(default_factory=list)


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

class ModelBenchmark:
    """Führt Benchmarks für verschiedene Modelle durch."""

    def __init__(self, id_folder: str, input_file: str = "input.json"):
        self.id_folder = Path(id_folder)
        self.input_file = input_file
        self.input_path = self.id_folder / "input" / input_file
        self.results: List[ModelRun] = []

        # Input laden für Schicht-Infos
        self.input_data = self._load_input()
        self.schicht_count = len(self.input_data.get("Gruppen", []))

    def _load_input(self) -> Dict[str, Any]:
        """Lädt Input-JSON."""
        if not self.input_path.exists():
            print(f"❌ Input nicht gefunden: {self.input_path}")
            return {"Gruppen": []}
        with open(self.input_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_all_models(self) -> BenchmarkResult:
        """Führt Benchmark für alle Modelle durch."""
        print("\n" + "=" * 70)
        print("🏁 MODEL BENCHMARK GESTARTET")
        print("=" * 70)
        print(f"📁 Input: {self.input_path}")
        print(f"📊 Schichten: {self.schicht_count}")
        print(f"🤖 Modelle: {', '.join(MODELS)}")
        print("=" * 70 + "\n")

        for i, model in enumerate(MODELS, 1):
            print(f"\n{'─' * 70}")
            print(f"[{i}/{len(MODELS)}] 🚀 Starte: {model}")
            print(f"{'─' * 70}")

            run_result = self._run_single_model(model)
            self.results.append(run_result)

            # Kurze Zusammenfassung nach jedem Run
            if not run_result.error:
                print(f"\n✅ {model} abgeschlossen:")
                print(f"   ⏱️  Zeit: {run_result.duration_seconds:.1f}s")
                print(f"   🔢 Tokens: {run_result.total_tokens:,}")
                print(f"   💵 Kosten: ${run_result.cost_usd:.6f}")
            else:
                print(f"\n❌ {model} fehlgeschlagen: {run_result.error}")

        return BenchmarkResult(
            timestamp=datetime.now().isoformat(),
            input_file=str(self.input_path),
            total_schichten=self.schicht_count,
            runs=self.results
        )

    def _run_single_model(self, model: str) -> ModelRun:
        """Führt einen einzelnen Modell-Durchlauf durch."""
        start_time = datetime.now()

        # Environment für Subprocess setzen
        env = os.environ.copy()
        env["AZURE_DEPLOYMENT"] = model

        # Output-Datei für dieses Modell
        output_file = f"output_{model}.json"
        output_path = self.id_folder / "output" / output_file

        # Sicherstellen dass Output-Ordner existiert
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # main.py ausführen
            result = subprocess.run(
                [
                    sys.executable, "main.py",
                    str(self.id_folder),
                    "--input-file", self.input_file,
                    "--output-file", output_file
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=600,  # 10 Minuten Timeout
                cwd=str(Path(__file__).parent)
            )

            duration = (datetime.now() - start_time).total_seconds()

            # Output parsen
            stdout = result.stdout

            # Tokens extrahieren
            tokens = self._extract_tokens(stdout)

            # Kosten berechnen
            prices = MODEL_PRICES.get(model, {"input": 1.0, "output": 4.0})
            cost_usd = (tokens["input"] / 1_000_000) * prices["input"] + \
                       (tokens["output"] / 1_000_000) * prices["output"]
            cost_eur = cost_usd * 0.92

            # Schicht-Ergebnisse aus Output-JSON laden
            schichten = self._parse_output(output_path)

            return ModelRun(
                model=model,
                start_time=start_time.isoformat(),
                duration_seconds=duration,
                input_tokens=tokens["input"],
                output_tokens=tokens["output"],
                total_tokens=tokens["total"],
                cost_usd=cost_usd,
                cost_eur=cost_eur,
                schichten=schichten
            )

        except subprocess.TimeoutExpired:
            return ModelRun(
                model=model,
                start_time=start_time.isoformat(),
                duration_seconds=600,
                input_tokens=0, output_tokens=0, total_tokens=0,
                cost_usd=0, cost_eur=0,
                error="Timeout nach 10 Minuten"
            )
        except Exception as e:
            return ModelRun(
                model=model,
                start_time=start_time.isoformat(),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                input_tokens=0, output_tokens=0, total_tokens=0,
                cost_usd=0, cost_eur=0,
                error=str(e)
            )

    def _extract_tokens(self, stdout: str) -> Dict[str, int]:
        """Extrahiert Token-Zahlen aus stdout."""
        import re

        # Suche nach Kosten-Zusammenfassung
        input_match = re.search(r"Input Tokens:\s*([\d,]+)", stdout)
        output_match = re.search(r"Output Tokens:\s*([\d,]+)", stdout)
        total_match = re.search(r"Gesamt Tokens:\s*([\d,]+)", stdout)

        def parse_num(match):
            if match:
                return int(match.group(1).replace(",", ""))
            return 0

        return {
            "input": parse_num(input_match),
            "output": parse_num(output_match),
            "total": parse_num(total_match)
        }

    def _parse_output(self, output_path: Path) -> List[SchichtResult]:
        """Parst Output-JSON für Schicht-Details."""
        if not output_path.exists():
            return []

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            return []

        schichten = []
        for gruppe in data.get("Gruppen", []):
            ids = gruppe.get("id", [])
            confidence = gruppe.get("id_confidence", {})

            # Top-Match ermitteln
            top_id = ids[0] if ids else ""
            top_conf = confidence.get(top_id, 0) if top_id else 0

            schichten.append(SchichtResult(
                name=gruppe.get("NAME", ""),
                material=gruppe.get("MATERIAL", ""),
                match_count=len(ids),
                top_match_id=top_id,
                top_confidence=top_conf,
                all_ids=ids
            ))

        return schichten


# =============================================================================
# AUSGABE / REPORTING
# =============================================================================

def print_comparison_table(result: BenchmarkResult) -> None:
    """Gibt übersichtliche Vergleichstabelle aus."""

    print("\n" + "=" * 90)
    print("📊 BENCHMARK ERGEBNISSE - ÜBERSICHT")
    print("=" * 90)

    # Header
    print(f"\n{'Modell':<16} {'Zeit':>8} {'Input':>10} {'Output':>10} {'Total':>10} {'Kosten $':>12} {'€':>10}")
    print("-" * 90)

    # Sortiert nach Kosten
    sorted_runs = sorted(result.runs, key=lambda x: x.cost_usd)

    for run in sorted_runs:
        if run.error:
            print(f"{run.model:<16} {'ERROR':>8} {'-':>10} {'-':>10} {'-':>10} {'-':>12} {'-':>10}")
            print(f"   ❌ {run.error}")
        else:
            print(
                f"{run.model:<16} {run.duration_seconds:>7.1f}s {run.input_tokens:>10,} {run.output_tokens:>10,} {run.total_tokens:>10,} ${run.cost_usd:>10.6f} €{run.cost_eur:>9.6f}")

    print("-" * 90)

    # Günstigstes Modell markieren
    cheapest = sorted_runs[0]
    if not cheapest.error:
        print(f"\n🏆 Günstigstes: {cheapest.model} (${cheapest.cost_usd:.6f})")

    # Schnellstes Modell
    fastest = min([r for r in result.runs if not r.error], key=lambda x: x.duration_seconds, default=None)
    if fastest:
        print(f"⚡ Schnellstes: {fastest.model} ({fastest.duration_seconds:.1f}s)")


def print_schicht_comparison(result: BenchmarkResult) -> None:
    """Gibt Schicht-für-Schicht Vergleich aus."""

    print("\n" + "=" * 90)
    print("📋 ERGEBNISSE PRO SCHICHT")
    print("=" * 90)

    # Finde erfolgreiche Runs
    valid_runs = [r for r in result.runs if not r.error and r.schichten]

    if not valid_runs:
        print("Keine gültigen Ergebnisse zum Vergleichen.")
        return

    schicht_count = len(valid_runs[0].schichten)

    for i in range(schicht_count):
        print(f"\n{'─' * 90}")
        schicht_info = valid_runs[0].schichten[i]
        print(f"Schicht {i + 1}: {schicht_info.name}")
        print(f"Material: {schicht_info.material}")
        print(f"{'─' * 90}")

        print(f"{'Modell':<16} {'Matches':>8} {'Top Confidence':>15} {'Top Match ID':<40}")
        print("-" * 90)

        for run in valid_runs:
            if i < len(run.schichten):
                s = run.schichten[i]
                conf_str = f"{s.top_confidence}%" if s.top_confidence else "N/A"
                print(f"{run.model:<16} {s.match_count:>8} {conf_str:>15} {s.top_match_id:<40}")

        # Prüfe ob alle Modelle gleiche Top-ID haben
        top_ids = [run.schichten[i].top_match_id for run in valid_runs if i < len(run.schichten)]
        if len(set(top_ids)) == 1 and top_ids[0]:
            print(f"✅ Alle Modelle: gleiche Top-ID")
        elif len(set(top_ids)) > 1:
            print(f"⚠️  Unterschiedliche Top-IDs!")


def save_results(result: BenchmarkResult, output_path: Path) -> None:
    """Speichert Ergebnisse als JSON."""

    # Konvertiere zu dict
    def to_dict(obj):
        if hasattr(obj, '__dict__'):
            return {k: to_dict(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [to_dict(item) for item in obj]
        return obj

    result_dict = to_dict(result)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Ergebnisse gespeichert: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Benchmark für Azure OpenAI Modelle'
    )
    parser.add_argument(
        'id_folder',
        type=str,
        help='Pfad zum ID-Ordner (wie bei main.py)'
    )
    parser.add_argument(
        '--input-file',
        type=str,
        default='input.json',
        help='Name der Input-JSON-Datei'
    )
    parser.add_argument(
        '--models',
        type=str,
        nargs='+',
        default=MODELS,
        help=f'Modelle zum Testen (Standard: {MODELS})'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Pfad für JSON-Ergebnis (optional)'
    )

    args = parser.parse_args()

    # Modelle überschreiben falls angegeben
    global MODELS
    MODELS = args.models

    # Benchmark durchführen
    benchmark = ModelBenchmark(args.id_folder, args.input_file)
    result = benchmark.run_all_models()

    # Ergebnisse ausgeben
    print_comparison_table(result)
    print_schicht_comparison(result)

    # Optional als JSON speichern
    if args.output:
        save_results(result, Path(args.output))
    else:
        # Standard: im Output-Ordner speichern
        default_output = Path(args.id_folder) / "output" / "benchmark_results.json"
        save_results(result, default_output)

    print("\n" + "=" * 90)
    print("✅ BENCHMARK ABGESCHLOSSEN")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    main()