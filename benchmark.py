#!/usr/bin/env python3
"""
Benchmark-Skript für Azure OpenAI Modell-Vergleich.
Fix: Unicode/Encoding Support für Windows & Robustere Token-Extraktion.
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

# UTF-8 für Konsole sicherstellen
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding="utf-8")

# =============================================================================
# KONFIGURATION
# =============================================================================

DEFAULT_MODELS = [
    "gpt-4o-mini",
    "gpt-5-nano",
    "gpt-5-chat",
    "gpt-5.2-chat",
]

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
    name: str
    material: str
    match_count: int
    top_match_id: str = ""
    top_confidence: int = 0


@dataclass
class ModelRun:
    model: str
    duration_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    schichten: List[SchichtResult] = field(default_factory=list)
    error: str = ""


@dataclass
class BenchmarkResult:
    timestamp: str
    input_file: str
    runs: List[ModelRun] = field(default_factory=list)


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

class ModelBenchmark:
    def __init__(self, base_folder: str, input_file: str, output_folder_name: str):
        self.base_path = Path(base_folder)
        self.input_path = self.base_path / "input" / input_file
        self.output_dir = self.base_path / output_folder_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[ModelRun] = []

    def run_benchmark(self, models: List[str]) -> BenchmarkResult:
        print(f"🚀 Starte Benchmark im Ordner: {self.base_path}")
        print(f"📂 Input: {self.input_path}")
        print(f"📁 Benchmark-Output: {self.output_dir}\n")

        for model in models:
            print(f"--- Teste Modell: {model} ---")
            run_result = self._execute_main(model)
            self.results.append(run_result)

            if run_result.error:
                print(f"❌ Fehler bei {model}: {run_result.error}")
            else:
                print(f"✅ Fertig: {run_result.duration_seconds:.1f}s | Cost: ${run_result.cost_usd:.5f}")

        return BenchmarkResult(
            timestamp=datetime.now().isoformat(),
            input_file=str(self.input_path),
            runs=self.results
        )

    def _execute_main(self, model: str) -> ModelRun:
        start_time = time.time()
        env = os.environ.copy()
        env["AZURE_DEPLOYMENT"] = model
        # Erzwingt UTF-8 Output auch im Subprozess
        env["PYTHONIOENCODING"] = "utf-8"

        output_filename = f"output_{model}.json"
        output_path = self.output_dir / output_filename

        try:
            # FIX: shell=True entfernt (sicherer) & encoding="utf-8" mit errors="replace"
            process = subprocess.run(
                [
                    sys.executable, "main.py",
                    str(self.base_path),
                    "--input-file", self.input_path.name,
                    "--output-file", str(Path(self.output_dir.name) / output_filename)
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=600,
                encoding="utf-8",  # FIX: Explizites UTF-8
                errors="replace"  # FIX: Ersetzt kaputte Zeichen statt abzustürzen
            )

            duration = time.time() - start_time
            tokens = self._extract_tokens(process.stdout or "")

            prices = MODEL_PRICES.get(model, {"input": 0, "output": 0})
            cost = (tokens["input"] / 1e6 * prices["input"]) + (tokens["output"] / 1e6 * prices["output"])
            schichten = self._parse_output_json(output_path)

            return ModelRun(
                model=model,
                duration_seconds=duration,
                input_tokens=tokens["input"],
                output_tokens=tokens["output"],
                total_tokens=tokens["total"],
                cost_usd=cost,
                schichten=schichten
            )
        except Exception as e:
            return ModelRun(model=model, duration_seconds=0, error=str(e))

    def _extract_tokens(self, stdout: str) -> Dict[str, int]:
        import re
        tokens = {"input": 0, "output": 0, "total": 0}
        for key in tokens.keys():
            # Robustere Regex, die auch Tausender-Trennzeichen ignoriert
            match = re.search(fr"{key.capitalize()} Tokens:\s*([\d,.]+)", stdout)
            if match:
                raw_val = match.group(1).replace(",", "").replace(".", "")
                tokens[key] = int(raw_val)
        return tokens

    def _parse_output_json(self, path: Path) -> List[SchichtResult]:
        if not path.exists(): return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            results = []
            for g in data.get("Gruppen", []):
                ids = g.get("id", [])
                top_id = ids[0] if ids else ""
                results.append(SchichtResult(
                    name=g.get("NAME", ""),
                    material=g.get("MATERIAL", ""),
                    match_count=len(ids),
                    top_match_id=top_id,
                    top_confidence=g.get("id_confidence", {}).get(top_id, 0)
                ))
            return results
        except:
            return []


# =============================================================================
# REPORTING
# =============================================================================

def print_results(result: BenchmarkResult):
    print("\n" + "=" * 85)
    print(f"{'Modell':<15} | {'Zeit':>7} | {'Tokens (In/Out)':>20} | {'Kosten $':>10}")
    print("-" * 85)
    for run in result.runs:
        if run.error:
            print(f"{run.model:<15} | ERROR: {run.error[:40]}...")
        else:
            token_str = f"{run.input_tokens}/{run.output_tokens}"
            print(f"{run.model:<15} | {run.duration_seconds:>6.1f}s | {token_str:>20} | ${run.cost_usd:>9.5f}")
    print("=" * 85)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    BASE_DIR = "TestInput/id_aufruf_benutzer"
    INPUT_FILE = "input.json"
    BENCHMARK_OUT = "output_benchmark"

    benchmark = ModelBenchmark(BASE_DIR, INPUT_FILE, BENCHMARK_OUT)
    final_result = benchmark.run_benchmark(DEFAULT_MODELS)

    print_results(final_result)

    stats_path = Path(BASE_DIR) / BENCHMARK_OUT / "benchmark_stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(asdict(final_result), f, indent=2, ensure_ascii=False)

    print(f"\n💾 Statistik gespeichert in: {stats_path}")