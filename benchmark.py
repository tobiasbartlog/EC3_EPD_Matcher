#!/usr/bin/env python3
"""
Benchmark-Skript für Azure OpenAI Modell-Vergleich.
FIXED: Output-Pfad-Handling, Schicht-Parsing, EPD-Namen-Auflösung.
ERWEITERT: all_confidences für jeden Match.
ERWEITERT: Timestamped Output-Ordner mit .env Kopie.
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

# UTF-8 für Konsole sicherstellen
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding="utf-8")

# EPD API Import (optional, für Namen-Auflösung)
try:
    from api.auth import TokenManager
    from api.epd_client import EPDAPIClient

    EPD_API_AVAILABLE = True
except ImportError:
    EPD_API_AVAILABLE = False

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
    top_match_name: str = ""  # EPD-Name
    top_confidence: int = 0
    all_ids: List[str] = field(default_factory=list)
    all_names: List[str] = field(default_factory=list)  # Alle EPD-Namen
    all_confidences: List[int] = field(default_factory=list)  # Confidence pro Match


@dataclass
class ModelRun:
    model: str
    duration_seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cost_eur: float = 0.0
    schichten: List[SchichtResult] = field(default_factory=list)
    error: str = ""


@dataclass
class BenchmarkResult:
    timestamp: str
    input_file: str
    total_schichten: int
    output_dir: str = ""  # NEU: Speichert den Output-Ordner
    runs: List[ModelRun] = field(default_factory=list)


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

class ModelBenchmark:
    def __init__(self, base_folder: str, input_file: str = "input.json"):
        self.base_path = Path(base_folder)
        self.input_path = self.base_path / "input" / input_file

        # NEU: Timestamped Output-Ordner
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = self.base_path / "output" / f"run_{self.run_timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # NEU: .env kopieren falls vorhanden
        self._copy_env_file()

        self.results: List[ModelRun] = []

        # Input laden für Schicht-Count
        self.input_data = self._load_input()
        self.schicht_count = len(self.input_data.get("Gruppen", []))

        # NEU: Input auch in Output-Ordner kopieren für Reproduzierbarkeit
        if self.input_path.exists():
            shutil.copy(self.input_path, self.output_dir / "input.json")

        # EPD-Namen-Cache
        self.epd_names: Dict[str, str] = {}
        self._load_epd_names()

    def _copy_env_file(self):
        """Kopiert .env Datei in den Output-Ordner."""
        # Suche .env in verschiedenen Orten
        possible_env_paths = [
            Path(".env"),
            Path(__file__).parent / ".env",
            self.base_path / ".env",
        ]

        for env_path in possible_env_paths:
            if env_path.exists():
                shutil.copy(env_path, self.output_dir / ".env")
                print(f"📋 .env kopiert von: {env_path}")
                return

        print("⚠️  Keine .env Datei gefunden zum Kopieren")

    def _load_input(self) -> Dict[str, Any]:
        """Lädt Input-JSON."""
        if not self.input_path.exists():
            print(f"❌ Input nicht gefunden: {self.input_path}")
            return {"Gruppen": []}
        with open(self.input_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_epd_names(self):
        """Lädt EPD-Namen von der API für ID-Auflösung."""
        if not EPD_API_AVAILABLE:
            print("⚠️  EPD API nicht verfügbar - IDs werden ohne Namen angezeigt")
            return

        try:
            print("🔄 Lade EPD-Datenbank für Namen-Auflösung...")
            token_manager = TokenManager()
            api_client = EPDAPIClient(token_manager)

            # Alle EPDs laden (nur ID + Name)
            epds = api_client.list_epds()

            for epd in epds:
                epd_id = str(epd.get("id", ""))
                epd_name = epd.get("name", "")
                if epd_id:
                    self.epd_names[epd_id] = epd_name

            print(f"✅ {len(self.epd_names)} EPD-Namen geladen\n")

        except Exception as e:
            print(f"⚠️  Fehler beim Laden der EPD-Namen: {e}")
            print("   IDs werden ohne Namen angezeigt\n")

    def _get_epd_name(self, epd_id: str) -> str:
        """Gibt EPD-Namen für ID zurück."""
        return self.epd_names.get(str(epd_id), "")

    def run_benchmark(self, models: List[str]) -> BenchmarkResult:
        print("\n" + "=" * 80)
        print("🏁 MODEL BENCHMARK")
        print("=" * 80)
        print(f"📂 Basis:     {self.base_path}")
        print(f"📄 Input:     {self.input_path}")
        print(f"📁 Output:    {self.output_dir}")  # NEU
        print(f"📊 Schichten: {self.schicht_count}")
        print(f"🤖 Modelle:   {', '.join(models)}")
        print("=" * 80 + "\n")

        for i, model in enumerate(models, 1):
            print(f"\n{'─' * 80}")
            print(f"[{i}/{len(models)}] 🚀 Teste: {model}")
            print(f"{'─' * 80}")

            run_result = self._execute_main(model)
            self.results.append(run_result)

            if run_result.error:
                print(f"❌ Fehler: {run_result.error[:100]}")
            else:
                print(f"✅ Fertig: {run_result.duration_seconds:.1f}s | "
                      f"Tokens: {run_result.input_tokens:,}+{run_result.output_tokens:,} | "
                      f"Cost: ${run_result.cost_usd:.6f}")
                print(f"   Schichten: {len(run_result.schichten)} mit Ergebnissen")

        return BenchmarkResult(
            timestamp=datetime.now().isoformat(),
            input_file=str(self.input_path),
            total_schichten=self.schicht_count,
            output_dir=str(self.output_dir),  # NEU
            runs=self.results
        )

    def _execute_main(self, model: str) -> ModelRun:
        start_time = time.time()

        # Environment vorbereiten
        env = os.environ.copy()
        env["AZURE_DEPLOYMENT"] = model
        env["PYTHONIOENCODING"] = "utf-8"

        # Output-Datei für dieses Modell
        output_filename = f"output_{model}.json"
        # main.py schreibt in den Standard-Output-Ordner
        default_output_path = self.base_path / "output" / output_filename
        # Wir wollen es hier haben
        final_output_path = self.output_dir / output_filename

        try:
            # main.py ausführen - nur Dateiname übergeben (main.py nutzt seinen Standard-Pfad)
            process = subprocess.run(
                [
                    sys.executable, "main.py",
                    str(self.base_path),
                    "--input-file", self.input_path.name,
                    "--output-file", output_filename  # Nur Dateiname!
                ],
                capture_output=True,
                text=True,
                env=env,
                timeout=600,
                encoding="utf-8",
                errors="replace",
                cwd=str(Path(__file__).parent)
            )

            # Output-Datei in den timestamped Ordner verschieben
            if default_output_path.exists():
                shutil.move(str(default_output_path), str(final_output_path))

            duration = time.time() - start_time

            # Debug: Zeige stderr falls Fehler
            if process.returncode != 0:
                print(f"⚠️  Return Code: {process.returncode}")
                if process.stderr:
                    print(f"   stderr: {process.stderr[:500]}")

            # Tokens aus stdout extrahieren
            tokens = self._extract_tokens(process.stdout or "")

            # Kosten berechnen
            prices = MODEL_PRICES.get(model, {"input": 0.15, "output": 0.60})
            cost_usd = (tokens["input"] / 1e6 * prices["input"]) + \
                       (tokens["output"] / 1e6 * prices["output"])
            cost_eur = cost_usd * 0.92

            # Schicht-Ergebnisse aus Output-JSON laden (aus dem timestamped Ordner)
            schichten = self._parse_output_json(final_output_path)

            return ModelRun(
                model=model,
                duration_seconds=duration,
                input_tokens=tokens["input"],
                output_tokens=tokens["output"],
                total_tokens=tokens["input"] + tokens["output"],
                cost_usd=cost_usd,
                cost_eur=cost_eur,
                schichten=schichten
            )

        except subprocess.TimeoutExpired:
            return ModelRun(
                model=model,
                duration_seconds=600,
                error="Timeout nach 10 Minuten"
            )
        except Exception as e:
            return ModelRun(
                model=model,
                duration_seconds=time.time() - start_time,
                error=str(e)
            )

    def _extract_tokens(self, stdout: str) -> Dict[str, int]:
        """Extrahiert Token-Zahlen aus stdout."""
        import re
        tokens = {"input": 0, "output": 0}

        # Suche nach "Input Tokens: X" und "Output Tokens: X"
        input_match = re.search(r"Input Tokens:\s*([\d,\.]+)", stdout)
        output_match = re.search(r"Output Tokens:\s*([\d,\.]+)", stdout)

        if input_match:
            tokens["input"] = int(input_match.group(1).replace(",", "").replace(".", ""))
        if output_match:
            tokens["output"] = int(output_match.group(1).replace(",", "").replace(".", ""))

        # Fallback: Suche nach "X in + Y out" Pattern
        if tokens["input"] == 0:
            alt_match = re.search(r"(\d+(?:,\d+)*)\s*in\s*\+\s*(\d+(?:,\d+)*)\s*out", stdout)
            if alt_match:
                tokens["input"] = int(alt_match.group(1).replace(",", ""))
                tokens["output"] = int(alt_match.group(2).replace(",", ""))

        return tokens

    def _parse_output_json(self, path: Path) -> List[SchichtResult]:
        """Parst Output-JSON für Schicht-Details mit allen Confidences."""
        if not path.exists():
            print(f"   ⚠️  Output nicht gefunden: {path}")
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            results = []
            for g in data.get("Gruppen", []):
                ids = g.get("id", [])
                confidence_map = g.get("id_confidence", {})

                # IDs als Strings
                all_ids_str = [str(i) for i in ids]

                # Top-Match
                top_id = all_ids_str[0] if all_ids_str else ""
                top_conf = confidence_map.get(top_id, 0) if top_id else 0

                # EPD-Namen auflösen
                all_names = [self._get_epd_name(i) for i in all_ids_str]
                top_name = self._get_epd_name(top_id) if top_id else ""

                # Confidence für JEDEN Match aus der Map holen
                all_confidences = []
                for id_str in all_ids_str:
                    conf = confidence_map.get(id_str, 0)
                    # Falls ID als int in der Map ist
                    if conf == 0:
                        conf = confidence_map.get(int(id_str) if id_str.isdigit() else id_str, 0)
                    all_confidences.append(conf)

                results.append(SchichtResult(
                    name=g.get("NAME", ""),
                    material=g.get("MATERIAL", ""),
                    match_count=len(ids),
                    top_match_id=top_id,
                    top_match_name=top_name,
                    top_confidence=top_conf,
                    all_ids=all_ids_str,
                    all_names=all_names,
                    all_confidences=all_confidences
                ))

            return results

        except Exception as e:
            print(f"   ⚠️  Fehler beim Parsen: {e}")
            return []


# =============================================================================
# REPORTING
# =============================================================================

def print_overview_table(result: BenchmarkResult):
    """Gibt übersichtliche Vergleichstabelle aus."""
    print("\n" + "=" * 95)
    print("📊 ÜBERSICHT - Sortiert nach Kosten")
    print("=" * 95)

    # Header
    print(f"{'Modell':<16} {'Zeit':>8} {'Input':>10} {'Output':>10} {'Total':>10} {'USD':>12} {'EUR':>10}")
    print("-" * 95)

    # Sortiert nach Kosten
    valid_runs = [r for r in result.runs if not r.error]
    sorted_runs = sorted(valid_runs, key=lambda x: x.cost_usd)

    for run in sorted_runs:
        print(f"{run.model:<16} {run.duration_seconds:>7.1f}s "
              f"{run.input_tokens:>10,} {run.output_tokens:>10,} {run.total_tokens:>10,} "
              f"${run.cost_usd:>10.6f} €{run.cost_eur:>9.6f}")

    # Fehler-Runs
    error_runs = [r for r in result.runs if r.error]
    for run in error_runs:
        print(f"{run.model:<16} {'ERROR':<8} {run.error[:60]}...")

    print("-" * 95)

    if sorted_runs:
        cheapest = sorted_runs[0]
        fastest = min(valid_runs, key=lambda x: x.duration_seconds)
        print(f"\n🏆 Günstigstes: {cheapest.model} (${cheapest.cost_usd:.6f})")
        print(f"⚡ Schnellstes: {fastest.model} ({fastest.duration_seconds:.1f}s)")


def print_schicht_comparison(result: BenchmarkResult):
    """Gibt Schicht-für-Schicht Vergleich aus."""
    print("\n" + "=" * 120)
    print("📋 ERGEBNISSE PRO SCHICHT")
    print("=" * 120)

    valid_runs = [r for r in result.runs if not r.error and r.schichten]

    if not valid_runs:
        print("Keine gültigen Ergebnisse zum Vergleichen.")
        return

    schicht_count = max(len(r.schichten) for r in valid_runs)

    for i in range(schicht_count):
        # Schicht-Info vom ersten Run
        schicht_info = None
        for run in valid_runs:
            if i < len(run.schichten):
                schicht_info = run.schichten[i]
                break

        if not schicht_info:
            continue

        print(f"\n{'─' * 120}")
        print(f"Schicht {i + 1}: {schicht_info.name}")
        print(f"Material: {schicht_info.material}")
        print(f"{'─' * 120}")

        print(f"{'Modell':<16} {'#':>3} {'Conf':>6} {'ID':>6}  {'EPD-Name':<80}")
        print("-" * 120)

        top_ids = []
        for run in valid_runs:
            if i < len(run.schichten):
                s = run.schichten[i]
                conf_str = f"{s.top_confidence}%" if s.top_confidence else "N/A"
                epd_name = s.top_match_name[:75] if s.top_match_name else "(Name nicht verfügbar)"
                print(f"{run.model:<16} {s.match_count:>3} {conf_str:>6} {s.top_match_id:>6}  {epd_name:<80}")
                top_ids.append(s.top_match_id)

        # Konsistenz-Check
        unique_ids = set(t for t in top_ids if t)
        if len(unique_ids) == 1:
            print(f"✅ Alle Modelle: gleiche Top-ID ({list(unique_ids)[0]})")
        elif len(unique_ids) > 1:
            print(f"⚠️  Unterschiedliche Top-IDs: {unique_ids}")

        # Zeige alle Matches für das erste Modell (als Referenz)
        if valid_runs and valid_runs[0].schichten and i < len(valid_runs[0].schichten):
            ref = valid_runs[0].schichten[i]
            if ref.all_names and any(ref.all_names):
                print(f"\n   📝 Alle Matches ({valid_runs[0].model}):")
                for idx, (mid, mname, mconf) in enumerate(zip(ref.all_ids[:5], ref.all_names[:5], ref.all_confidences[
                    :5] if ref.all_confidences else [0] * 5), 1):
                    name_display = mname[:65] if mname else "(kein Name)"
                    conf_display = f"{mconf}%" if mconf else "?"
                    print(f"      {idx}. ID {mid} ({conf_display}): {name_display}")


def print_cost_comparison(result: BenchmarkResult):
    """Zeigt Kosten-Vergleich und Spar-Potenzial."""
    print("\n" + "=" * 95)
    print("💰 KOSTEN-ANALYSE")
    print("=" * 95)

    valid_runs = [r for r in result.runs if not r.error]
    if len(valid_runs) < 2:
        return

    sorted_runs = sorted(valid_runs, key=lambda x: x.cost_usd)
    cheapest = sorted_runs[0]
    most_expensive = sorted_runs[-1]

    print(f"\nGünstigstes Modell:  {cheapest.model:<16} ${cheapest.cost_usd:.6f}")
    print(f"Teuerstes Modell:    {most_expensive.model:<16} ${most_expensive.cost_usd:.6f}")

    if most_expensive.cost_usd > 0:
        savings = (1 - cheapest.cost_usd / most_expensive.cost_usd) * 100
        factor = most_expensive.cost_usd / cheapest.cost_usd if cheapest.cost_usd > 0 else 0
        print(f"\nErsparnis mit {cheapest.model}: {savings:.1f}% (Faktor {factor:.1f}x günstiger)")

    # Hochrechnung für 1000 Requests
    print(f"\n📈 Hochrechnung für 1000 Batch-Requests:")
    print("-" * 50)
    for run in sorted_runs:
        cost_1k = run.cost_usd * 1000
        print(f"   {run.model:<16} ${cost_1k:>10.2f}")


def print_detailed_matches(result: BenchmarkResult):
    """Zeigt detaillierten Match-Vergleich mit allen EPD-Namen und Confidences."""
    print("\n" + "=" * 130)
    print("🔍 DETAILLIERTER MATCH-VERGLEICH (Top 5 pro Modell)")
    print("=" * 130)

    valid_runs = [r for r in result.runs if not r.error and r.schichten]
    if not valid_runs:
        return

    schicht_count = max(len(r.schichten) for r in valid_runs)

    for i in range(schicht_count):
        schicht_info = None
        for run in valid_runs:
            if i < len(run.schichten):
                schicht_info = run.schichten[i]
                break

        if not schicht_info:
            continue

        print(f"\n{'━' * 130}")
        print(f"SCHICHT {i + 1}: {schicht_info.name} | Material: {schicht_info.material}")
        print(f"{'━' * 130}")

        for run in valid_runs:
            if i >= len(run.schichten):
                continue

            s = run.schichten[i]
            print(f"\n  📌 {run.model} ({s.match_count} Matches):")

            # Zip mit Confidences (falls vorhanden)
            confidences = s.all_confidences if s.all_confidences else [0] * len(s.all_ids)

            for idx, (mid, mname, mconf) in enumerate(zip(s.all_ids[:5], s.all_names[:5], confidences[:5]), 1):
                name_display = mname[:80] if mname else "(Name nicht geladen)"
                marker = "→" if idx == 1 else " "
                conf_str = f"[{mconf:>3}%]" if mconf else "[  ?%]"
                print(f"     {marker} {idx}. {conf_str} [{mid:>4}] {name_display}")


def save_results(result: BenchmarkResult, output_path: Path):
    """Speichert Ergebnisse als JSON."""

    # Konvertiere dataclasses zu dict
    def convert(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return {k: convert(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, list):
            return [convert(i) for i in obj]
        return obj

    result_dict = convert(result)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Ergebnisse gespeichert: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Benchmark für Azure OpenAI Modelle')
    parser.add_argument(
        'id_folder',
        type=str,
        nargs='?',
        default="TestInput/id_aufruf_benutzer",
        help='Pfad zum ID-Ordner (Standard: TestInput/id_aufruf_benutzer)'
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
        default=DEFAULT_MODELS,
        help=f'Modelle zum Testen'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Pfad für JSON-Ergebnis (überschreibt automatischen Pfad)'
    )

    args = parser.parse_args()

    # Benchmark durchführen
    benchmark = ModelBenchmark(args.id_folder, args.input_file)
    result = benchmark.run_benchmark(args.models)

    # Ergebnisse ausgeben
    print_overview_table(result)
    print_schicht_comparison(result)
    print_detailed_matches(result)
    print_cost_comparison(result)

    # Speichern - im timestamped Ordner
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = benchmark.output_dir / "benchmark_results.json"

    save_results(result, output_path)

    print("\n" + "=" * 95)
    print(f"✅ BENCHMARK ABGESCHLOSSEN")
    print(f"📁 Alle Ergebnisse in: {benchmark.output_dir}")
    print("=" * 95 + "\n")


if __name__ == "__main__":
    main()