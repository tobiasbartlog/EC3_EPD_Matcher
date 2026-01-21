#!/usr/bin/env python3
"""
Benchmark-Auswertungstool für Azure OpenAI Modell-Vergleich.

Liest benchmark_results.json und erstellt übersichtliche Auswertungen.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

# UTF-8 für Konsole
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding="utf-8")


# =============================================================================
# DATEN LADEN
# =============================================================================

def load_results(path: str) -> Dict[str, Any]:
    """Lädt Benchmark-Ergebnisse aus JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# ÜBERSICHTS-TABELLEN
# =============================================================================

def print_header(title: str, width: int = 100):
    """Druckt formatierte Überschrift."""
    print(f"\n{'═' * width}")
    print(f" {title}")
    print(f"{'═' * width}")


def print_cost_overview(data: Dict[str, Any]):
    """Zeigt Kosten-Übersicht sortiert nach Preis."""
    print_header("💰 KOSTEN-ÜBERSICHT (sortiert nach Preis)", 100)

    runs = [r for r in data["runs"] if not r.get("error")]
    runs_sorted = sorted(runs, key=lambda x: x["cost_usd"])

    # Header
    print(
        f"\n{'Modell':<16} {'Zeit':>8} {'Input':>8} {'Output':>8} {'Total':>8} {'$/1M in':>8} {'$/1M out':>9} {'Kosten $':>12}")
    print("─" * 100)

    cheapest_cost = runs_sorted[0]["cost_usd"] if runs_sorted else 1

    for run in runs_sorted:
        # Effektive Preise berechnen
        eff_input = (run["cost_usd"] * 1_000_000 / run["input_tokens"]) if run["input_tokens"] else 0
        eff_output = (run["cost_usd"] * 1_000_000 / run["output_tokens"]) if run["output_tokens"] else 0

        factor = run["cost_usd"] / cheapest_cost if cheapest_cost else 1
        factor_str = f"(×{factor:.1f})" if factor > 1.1 else "(🏆)"

        print(f"{run['model']:<16} {run['duration_seconds']:>7.1f}s "
              f"{run['input_tokens']:>8,} {run['output_tokens']:>8,} {run['total_tokens']:>8,} "
              f"${eff_input:>7.2f} ${eff_output:>8.2f} "
              f"${run['cost_usd']:>10.6f} {factor_str}")

    print("─" * 100)

    # Zusammenfassung
    if len(runs_sorted) >= 2:
        cheapest = runs_sorted[0]
        most_exp = runs_sorted[-1]
        savings = (1 - cheapest["cost_usd"] / most_exp["cost_usd"]) * 100

        print(f"\n🏆 Günstigstes:   {cheapest['model']} (${cheapest['cost_usd']:.6f})")
        print(f"💸 Teuerstes:     {most_exp['model']} (${most_exp['cost_usd']:.6f})")
        print(f"📉 Max. Ersparnis: {savings:.1f}%")


def print_speed_overview(data: Dict[str, Any]):
    """Zeigt Geschwindigkeits-Übersicht."""
    print_header("⚡ GESCHWINDIGKEITS-ÜBERSICHT", 100)

    runs = [r for r in data["runs"] if not r.get("error")]
    runs_sorted = sorted(runs, key=lambda x: x["duration_seconds"])

    print(f"\n{'Modell':<16} {'Zeit':>10} {'Tokens/s':>12} {'Output Tok':>12} {'Out Tok/s':>12}")
    print("─" * 70)

    for run in runs_sorted:
        total_tps = run["total_tokens"] / run["duration_seconds"] if run["duration_seconds"] else 0
        out_tps = run["output_tokens"] / run["duration_seconds"] if run["duration_seconds"] else 0

        print(f"{run['model']:<16} {run['duration_seconds']:>9.1f}s "
              f"{total_tps:>11.1f} {run['output_tokens']:>12,} {out_tps:>11.1f}")

    print("─" * 70)

    if runs_sorted:
        fastest = runs_sorted[0]
        slowest = runs_sorted[-1]
        print(f"\n⚡ Schnellstes: {fastest['model']} ({fastest['duration_seconds']:.1f}s)")
        print(f"🐢 Langsamstes: {slowest['model']} ({slowest['duration_seconds']:.1f}s)")


def print_quality_overview(data: Dict[str, Any]):
    """Zeigt Qualitäts-Übersicht (Confidence-Werte)."""
    print_header("🎯 QUALITÄTS-ÜBERSICHT (Durchschn. Confidence)", 100)

    runs = [r for r in data["runs"] if not r.get("error") and r.get("schichten")]

    print(f"\n{'Modell':<16} {'Ø Conf':>8} {'Max':>6} {'Min':>6} {'Matches':>8} {'Schichten':>10}")
    print("─" * 60)

    model_stats = []
    for run in runs:
        confidences = [s["top_confidence"] for s in run["schichten"] if s.get("top_confidence")]
        total_matches = sum(s["match_count"] for s in run["schichten"])

        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            max_conf = max(confidences)
            min_conf = min(confidences)
        else:
            avg_conf = max_conf = min_conf = 0

        model_stats.append({
            "model": run["model"],
            "avg": avg_conf,
            "max": max_conf,
            "min": min_conf,
            "matches": total_matches,
            "schichten": len(run["schichten"])
        })

    # Sortiert nach durchschnittlicher Confidence
    model_stats.sort(key=lambda x: x["avg"], reverse=True)

    for s in model_stats:
        print(f"{s['model']:<16} {s['avg']:>7.1f}% {s['max']:>5}% {s['min']:>5}% "
              f"{s['matches']:>8} {s['schichten']:>10}")

    print("─" * 60)

    if model_stats:
        best = model_stats[0]
        print(f"\n🎯 Höchste Ø Confidence: {best['model']} ({best['avg']:.1f}%)")


# =============================================================================
# SCHICHT-VERGLEICH
# =============================================================================

def print_schicht_comparison(data: Dict[str, Any]):
    """Zeigt detaillierten Schicht-für-Schicht Vergleich."""
    print_header("📋 SCHICHT-FÜR-SCHICHT VERGLEICH", 120)

    runs = [r for r in data["runs"] if not r.get("error") and r.get("schichten")]
    if not runs:
        print("Keine Daten verfügbar.")
        return

    schicht_count = len(runs[0]["schichten"])

    for i in range(schicht_count):
        schicht = runs[0]["schichten"][i]

        print(f"\n{'━' * 120}")
        print(f"SCHICHT {i + 1}: {schicht['name']}")
        print(f"Material: {schicht['material']}")
        print(f"{'━' * 120}")

        print(f"\n{'Modell':<16} {'#':>3} {'Conf':>6} {'ID':>6}  {'Top Match EPD-Name':<75}")
        print("─" * 120)

        top_ids = []
        for run in runs:
            if i < len(run["schichten"]):
                s = run["schichten"][i]
                conf_str = f"{s['top_confidence']}%" if s.get("top_confidence") else "N/A"
                name = s.get("top_match_name", "")[:70]
                print(f"{run['model']:<16} {s['match_count']:>3} {conf_str:>6} "
                      f"{s['top_match_id']:>6}  {name:<75}")
                top_ids.append(s["top_match_id"])

        # Konsistenz-Check
        unique_ids = set(t for t in top_ids if t)
        if len(unique_ids) == 1:
            print(f"\n✅ KONSISTENT: Alle Modelle wählen ID {list(unique_ids)[0]}")
        elif len(unique_ids) > 1:
            print(f"\n⚠️  UNTERSCHIEDLICH: {len(unique_ids)} verschiedene Top-IDs")
            for uid in unique_ids:
                models = [runs[j]["model"] for j in range(len(runs))
                          if j < len(runs) and i < len(runs[j]["schichten"])
                          and runs[j]["schichten"][i]["top_match_id"] == uid]
                name = ""
                for run in runs:
                    if i < len(run["schichten"]) and run["schichten"][i]["top_match_id"] == uid:
                        name = run["schichten"][i].get("top_match_name", "")
                        break
                print(f"   ID {uid}: {', '.join(models)} → {name[:60]}")


def print_detailed_matches(data: Dict[str, Any]):
    """Zeigt alle Matches pro Schicht und Modell."""
    print_header("🔍 DETAILLIERTE MATCH-LISTE (Top 5 pro Modell)", 120)

    runs = [r for r in data["runs"] if not r.get("error") and r.get("schichten")]
    if not runs:
        return

    schicht_count = len(runs[0]["schichten"])

    for i in range(schicht_count):
        schicht = runs[0]["schichten"][i]

        print(f"\n{'━' * 120}")
        print(f"SCHICHT {i + 1}: {schicht['name']} | {schicht['material'][:80]}")
        print(f"{'━' * 120}")

        for run in runs:
            if i >= len(run["schichten"]):
                continue

            s = run["schichten"][i]
            conf_str = f"{s['top_confidence']}%" if s.get("top_confidence") else "?"
            print(f"\n  📌 {run['model']} ({s['match_count']} Matches, Top-Conf: {conf_str})")

            ids = s.get("all_ids", [])[:5]
            names = s.get("all_names", [])[:5]

            for idx, (mid, mname) in enumerate(zip(ids, names), 1):
                marker = "→" if idx == 1 else " "
                print(f"     {marker} {idx}. [{mid:>4}] {mname[:90]}")


# =============================================================================
# KONSISTENZ-ANALYSE
# =============================================================================

def print_consistency_analysis(data: Dict[str, Any]):
    """Analysiert Konsistenz der Ergebnisse zwischen Modellen."""
    print_header("🔄 KONSISTENZ-ANALYSE", 100)

    runs = [r for r in data["runs"] if not r.get("error") and r.get("schichten")]
    if len(runs) < 2:
        print("Mindestens 2 Modelle benötigt für Konsistenz-Analyse.")
        return

    schicht_count = len(runs[0]["schichten"])

    # Pro Schicht: Übereinstimmung der Top-IDs
    print(f"\n{'Schicht':<30} {'Top-ID Konsistenz':<25} {'Übereinstimmende Modelle'}")
    print("─" * 90)

    consistent_count = 0
    for i in range(schicht_count):
        schicht_name = runs[0]["schichten"][i]["name"]

        # Sammle Top-IDs
        top_ids = {}
        for run in runs:
            if i < len(run["schichten"]):
                tid = run["schichten"][i]["top_match_id"]
                if tid not in top_ids:
                    top_ids[tid] = []
                top_ids[tid].append(run["model"])

        # Finde häufigste ID
        most_common_id = max(top_ids.keys(), key=lambda x: len(top_ids[x]))
        agreement = len(top_ids[most_common_id])
        total = len(runs)

        if agreement == total:
            status = "✅ 100% Übereinstimmung"
            consistent_count += 1
        elif agreement >= total * 0.75:
            status = f"🟡 {agreement}/{total} stimmen überein"
        else:
            status = f"🔴 Nur {agreement}/{total}"

        models_str = ", ".join(top_ids[most_common_id])
        print(f"{schicht_name:<30} {status:<25} {models_str}")

    print("─" * 90)
    print(f"\n📊 Gesamt-Konsistenz: {consistent_count}/{schicht_count} Schichten "
          f"({consistent_count / schicht_count * 100:.0f}%) mit 100% Übereinstimmung")

    # Paarweise Übereinstimmung
    print(f"\n{'Modell-Paar':<35} {'Übereinstimmung':>15}")
    print("─" * 55)

    for j, run1 in enumerate(runs):
        for run2 in runs[j + 1:]:
            matches = 0
            for i in range(schicht_count):
                if i < len(run1["schichten"]) and i < len(run2["schichten"]):
                    if run1["schichten"][i]["top_match_id"] == run2["schichten"][i]["top_match_id"]:
                        matches += 1

            pair_name = f"{run1['model']} ↔ {run2['model']}"
            pct = matches / schicht_count * 100 if schicht_count else 0
            print(f"{pair_name:<35} {matches}/{schicht_count} ({pct:.0f}%)")


# =============================================================================
# EMPFEHLUNG
# =============================================================================

def print_recommendation(data: Dict[str, Any]):
    """Gibt Modell-Empfehlung basierend auf Analyse."""
    print_header("💡 EMPFEHLUNG", 100)

    runs = [r for r in data["runs"] if not r.get("error") and r.get("schichten")]
    if not runs:
        print("Keine Daten für Empfehlung.")
        return

    # Scoring
    scores = {}
    for run in runs:
        model = run["model"]

        # Kosten-Score (niedriger = besser)
        all_costs = [r["cost_usd"] for r in runs]
        cost_rank = sorted(all_costs).index(run["cost_usd"]) + 1
        cost_score = (len(runs) - cost_rank + 1) / len(runs) * 30  # Max 30 Punkte

        # Geschwindigkeits-Score (schneller = besser)
        all_times = [r["duration_seconds"] for r in runs]
        time_rank = sorted(all_times).index(run["duration_seconds"]) + 1
        time_score = (len(runs) - time_rank + 1) / len(runs) * 20  # Max 20 Punkte

        # Qualitäts-Score (höhere Confidence = besser)
        confidences = [s["top_confidence"] for s in run["schichten"] if s.get("top_confidence")]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        quality_score = avg_conf / 100 * 50  # Max 50 Punkte

        total = cost_score + time_score + quality_score
        scores[model] = {
            "cost_score": cost_score,
            "time_score": time_score,
            "quality_score": quality_score,
            "total": total,
            "cost": run["cost_usd"],
            "time": run["duration_seconds"],
            "avg_conf": avg_conf
        }

    # Sortiert nach Gesamt-Score
    ranked = sorted(scores.items(), key=lambda x: x[1]["total"], reverse=True)

    print(f"\n{'Modell':<16} {'Kosten':>8} {'Zeit':>8} {'Qualität':>10} {'GESAMT':>10}")
    print(f"{'':16} {'(30 max)':>8} {'(20 max)':>8} {'(50 max)':>10} {'(100 max)':>10}")
    print("─" * 60)

    for model, s in ranked:
        marker = "🏆" if model == ranked[0][0] else "  "
        print(f"{marker}{model:<14} {s['cost_score']:>8.1f} {s['time_score']:>8.1f} "
              f"{s['quality_score']:>10.1f} {s['total']:>10.1f}")

    print("─" * 60)

    winner = ranked[0]
    print(f"\n🏆 EMPFEHLUNG: {winner[0]}")
    print(f"   • Kosten: ${winner[1]['cost']:.6f}")
    print(f"   • Zeit: {winner[1]['time']:.1f}s")
    print(f"   • Ø Confidence: {winner[1]['avg_conf']:.1f}%")

    # Alternativen
    if len(ranked) >= 2:
        cheapest = min(runs, key=lambda x: x["cost_usd"])
        fastest = min(runs, key=lambda x: x["duration_seconds"])

        print(f"\n📌 Alternativen:")
        if cheapest["model"] != winner[0]:
            print(f"   • Günstigste Option: {cheapest['model']} (${cheapest['cost_usd']:.6f})")
        if fastest["model"] != winner[0]:
            print(f"   • Schnellste Option: {fastest['model']} ({fastest['duration_seconds']:.1f}s)")


# =============================================================================
# HOCHRECHNUNG
# =============================================================================

def print_cost_projection(data: Dict[str, Any]):
    """Zeigt Kosten-Hochrechnung für verschiedene Volumina."""
    print_header("📈 KOSTEN-HOCHRECHNUNG", 100)

    runs = [r for r in data["runs"] if not r.get("error")]
    runs_sorted = sorted(runs, key=lambda x: x["cost_usd"])

    volumes = [10, 100, 1000, 10000]

    print(f"\n{'Modell':<16}", end="")
    for v in volumes:
        print(f"{v:>12} Req", end="")
    print()
    print("─" * 80)

    for run in runs_sorted:
        print(f"{run['model']:<16}", end="")
        for v in volumes:
            cost = run["cost_usd"] * v
            if cost < 1:
                print(f"${cost:>13.4f}", end="")
            elif cost < 100:
                print(f"${cost:>13.2f}", end="")
            else:
                print(f"${cost:>13.0f}", end="")
        print()

    print("─" * 80)

    # Ersparnis bei 1000 Requests
    if len(runs_sorted) >= 2:
        cheap = runs_sorted[0]
        expensive = runs_sorted[-1]
        savings_1k = (expensive["cost_usd"] - cheap["cost_usd"]) * 1000
        print(f"\n💰 Ersparnis bei 1000 Requests mit {cheap['model']} statt {expensive['model']}: ${savings_1k:.2f}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Benchmark-Auswertungstool')
    parser.add_argument(
        'results_file',
        type=str,
        nargs='?',
        default="TestInput/id_aufruf_benutzer/output/benchmark_results.json",
        help='Pfad zur benchmark_results.json'
    )
    parser.add_argument(
        '--section',
        type=str,
        choices=['cost', 'speed', 'quality', 'schicht', 'detail', 'consistency', 'recommend', 'projection', 'all'],
        default='all',
        help='Welche Auswertung anzeigen'
    )

    args = parser.parse_args()

    # Daten laden
    try:
        data = load_results(args.results_file)
    except FileNotFoundError:
        print(f"❌ Datei nicht gefunden: {args.results_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ JSON-Fehler: {e}")
        sys.exit(1)

    print("\n" + "█" * 100)
    print("█  BENCHMARK AUSWERTUNG")
    print(f"█  Datei: {args.results_file}")
    print(f"█  Timestamp: {data.get('timestamp', 'N/A')}")
    print(f"█  Schichten: {data.get('total_schichten', 'N/A')}")
    print(f"█  Modelle: {len(data.get('runs', []))}")
    print("█" * 100)

    sections = {
        'cost': print_cost_overview,
        'speed': print_speed_overview,
        'quality': print_quality_overview,
        'schicht': print_schicht_comparison,
        'detail': print_detailed_matches,
        'consistency': print_consistency_analysis,
        'recommend': print_recommendation,
        'projection': print_cost_projection,
    }

    if args.section == 'all':
        for func in sections.values():
            func(data)
    else:
        sections[args.section](data)

    print("\n" + "═" * 100)
    print("✅ AUSWERTUNG ABGESCHLOSSEN")
    print("═" * 100 + "\n")


if __name__ == "__main__":
    main()