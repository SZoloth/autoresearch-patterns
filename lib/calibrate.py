#!/usr/bin/env python3
"""Calibrate benchmark stability and directionality before optimization."""

import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))
from parse_config import parse_config
from tui import (
    BOLD_CYAN, BOLD_GREEN, BOLD_RED, BOLD_WHITE, BOLD_YELLOW,
    DIM, GREEN, RED, RESET, YELLOW,
    banner, format_value,
)


def run_benchmark_once():
    """Run benchmark.sh once and return the metric value as a float.

    Returns None if the run fails or no METRIC line is found.
    """
    result = subprocess.run(
        ["bash", "benchmark.sh"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return None

    output = result.stdout + result.stderr

    # Use the last METRIC line (composite metrics emit components then final score)
    last_metric = None
    for line in output.split("\n"):
        if line.startswith("METRIC "):
            pair = line[7:]
            _key, _, val = pair.partition("=")
            try:
                last_metric = float(val)
            except (ValueError, TypeError):
                pass

    return last_metric


def run_benchmark_n(n=3, metric_name="", unit="", show_progress=True):
    """Run benchmark n times, displaying progress. Returns list of values."""
    values = []
    for i in range(n):
        if show_progress:
            print(f"  {DIM}Run {i + 1}/{n}...{RESET}", end="", flush=True)
        val = run_benchmark_once()
        if val is not None:
            val_str = format_value(val, unit)
            if show_progress:
                print(f"\r  Run {i + 1}: {BOLD_WHITE}{metric_name}{RESET} = {val_str}")
            values.append(val)
        else:
            if show_progress:
                print(f"\r  Run {i + 1}: {RED}failed{RESET}")
    return values


def compute_stability(values):
    """Compute stability metrics from a list of values.

    Returns dict with: median, mean, min, max, range, stdev, cv, verdict.
    """
    if len(values) < 2:
        return {
            "median": values[0] if values else 0,
            "mean": values[0] if values else 0,
            "min": values[0] if values else 0,
            "max": values[0] if values else 0,
            "range": 0,
            "stdev": 0,
            "cv": 0,
            "runs": len(values),
            "verdict": "insufficient data",
        }

    med = statistics.median(values)
    mean = statistics.mean(values)
    lo, hi = min(values), max(values)
    stdev = statistics.stdev(values)
    cv = (stdev / mean * 100) if mean != 0 else 0

    if cv < 5:
        verdict = "stable"
    elif cv < 10:
        verdict = "acceptable"
    else:
        verdict = "noisy"

    return {
        "median": med,
        "mean": mean,
        "min": lo,
        "max": hi,
        "range": hi - lo,
        "stdev": stdev,
        "cv": round(cv, 1),
        "runs": len(values),
        "verdict": verdict,
    }


def verdict_color(verdict):
    """Return ANSI color for a stability verdict."""
    if verdict == "stable":
        return GREEN
    elif verdict == "acceptable":
        return YELLOW
    return RED


def write_calibration_report(config, stability, directional=None):
    """Write calibration.md with findings."""
    metric = config["metric"]
    name = metric["name"]
    unit = metric.get("unit", "")
    direction = metric["direction"]

    med_str = format_value(stability["median"], unit)
    min_str = format_value(stability["min"], unit)
    max_str = format_value(stability["max"], unit)

    confidence = "high" if stability["verdict"] == "stable" else (
        "medium" if stability["verdict"] == "acceptable" else "low"
    )

    if confidence == "high":
        recommendation = "proceed"
    elif confidence == "low":
        recommendation = "investigate noise sources before running optimization"
    else:
        recommendation = "proceed with caution — consider strict rigor"

    lines = [
        "# Calibration Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Stability",
        "",
        f"- **Baseline:** {med_str} (median of {stability['runs']} runs)",
        f"- **Range:** {min_str} – {max_str}",
        f"- **CV:** {stability['cv']}% — {stability['verdict']}",
        "",
        "## Directionality",
        "",
    ]

    if directional is None:
        lines.append("- Skipped (non-interactive mode)")
    elif directional:
        lines.append("- **Pass** — metric responds to deliberate changes in the expected direction")
    else:
        lines.append("- **Fail** — metric did NOT respond as expected. The eval command may not measure what you think.")

    lines.extend([
        "",
        "## Assessment",
        "",
        f"- **Confidence:** {confidence}",
        f"- **Recommendation:** {recommendation}",
        "",
        "## For the optimization agent",
        "",
        f"- Use {med_str} as the authoritative baseline, not a single test run.",
    ])

    if stability["verdict"] == "noisy":
        lines.append(f"- Variance is high ({stability['cv']}% CV). Run experiments multiple times before concluding an improvement is real.")
        lines.append("- Consider using `rigor: strict` which requires 3x runs for baseline and confirmation.")
    elif stability["verdict"] == "acceptable":
        lines.append(f"- Variance is moderate ({stability['cv']}% CV). Treat improvements under {stability['cv'] * 2}% with skepticism.")

    lines.append("")

    Path("calibration.md").write_text("\n".join(lines))


def main():
    """Run the calibration flow."""
    config_path = "lab.yaml"
    runs = 3

    # Parse flags — --runs N and optional config path
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--runs" and i + 1 < len(sys.argv):
            runs = int(sys.argv[i + 1])
            i += 2
        elif not sys.argv[i].startswith("--"):
            config_path = sys.argv[i]
            i += 1
        else:
            i += 1

    if not Path(config_path).exists():
        print(f"Error: {config_path} not found. Run 'autoresearch init' first.", file=sys.stderr)
        sys.exit(1)

    if not Path("benchmark.sh").exists():
        print("Error: benchmark.sh not found. Run 'autoresearch init' first.", file=sys.stderr)
        sys.exit(1)

    config = parse_config(config_path)
    metric = config["metric"]
    metric_name = metric["name"]
    unit = metric.get("unit", "")
    direction = metric["direction"]

    print()
    print(f"  {BOLD_CYAN}{'━' * 44}{RESET}")
    print(f"  {BOLD_WHITE}  Calibrating: {config['name']}{RESET}")
    print(f"  {BOLD_CYAN}{'━' * 44}{RESET}")
    print()

    # Step 1: stability check
    print(f"  {BOLD_WHITE}Stability check{RESET} ({runs} runs on unmodified code)")
    print()

    values = run_benchmark_n(runs, metric_name, unit)

    if not values:
        print(f"\n  {BOLD_RED}All runs failed.{RESET} Fix your benchmark before calibrating.")
        sys.exit(1)

    if len(values) < runs:
        print(f"\n  {YELLOW}Warning: {runs - len(values)} of {runs} runs failed.{RESET}")

    stability = compute_stability(values)
    vc = verdict_color(stability["verdict"])

    print()
    print(f"  {BOLD_CYAN}{'━' * 44}{RESET}")
    print(f"  {BOLD_WHITE}  Calibration Report{RESET}")
    print(f"  {BOLD_CYAN}{'━' * 44}{RESET}")
    print()
    print(f"  {DIM}Baseline{RESET}     {BOLD_GREEN}{format_value(stability['median'], unit)}{RESET} {DIM}(median of {len(values)}){RESET}")
    print(f"  {DIM}Range{RESET}        {format_value(stability['min'], unit)} – {format_value(stability['max'], unit)}")
    print(f"  {DIM}CV{RESET}           {vc}{stability['cv']}% — {stability['verdict']}{RESET}")

    if stability["verdict"] == "noisy":
        print()
        print(f"  {BOLD_YELLOW}High variance detected.{RESET}")
        print(f"  {DIM}Consider: closing background processes, using 'rigor: strict',{RESET}")
        print(f"  {DIM}or adding warmup runs to your eval command.{RESET}")

    # Write report (directional probe skipped in non-interactive CLI mode)
    write_calibration_report(config, stability, directional=None)

    print()
    print(f"  {DIM}Written to{RESET} calibration.md")
    print()

    # Stage calibration.md if in a git repo
    subprocess.run(["git", "add", "calibration.md"], capture_output=True)

    print(f"  {DIM}Next:{RESET} {BOLD_WHITE}autoresearch start{RESET}")
    print()


if __name__ == "__main__":
    main()
