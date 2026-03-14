#!/usr/bin/env python3
"""Display formatted status summary of an autoresearch session."""

import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))
from parse_config import parse_config
from tui import (
    BOLD, BOLD_GREEN, BOLD_WHITE, BOLD_YELLOW, DIM, GREEN, RED, RESET, YELLOW,
    count_streak, format_delta, format_value, header, sparkline,
)


def read_results(path):
    """Parse results.tsv into list of dicts."""
    if not Path(path).exists():
        return []
    lines = Path(path).read_text().strip().split("\n")
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = line.split("\t")
        row = {}
        for i, h in enumerate(headers):
            row[h] = fields[i] if i < len(fields) else ""
        rows.append(row)
    return rows


def extract_best_and_baseline(results, metric_name, direction):
    """Extract best value and baseline from results list.

    Returns (best, baseline) tuple. Both may be None if no valid values exist.
    """
    vals = []
    for r in results:
        try:
            vals.append(float(r.get(metric_name, "")))
        except (ValueError, TypeError):
            pass
    if not vals:
        return None, None
    baseline = vals[0]
    best = min(vals) if direction == "lower" else max(vals)
    return best, baseline


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "lab.yaml"

    if not Path(config_path).exists():
        print("No lab.yaml found. Run 'autoresearch init' first.", file=sys.stderr)
        sys.exit(1)

    config = parse_config(config_path)
    metric = config["metric"]
    metric_name = metric["name"]
    direction = metric["direction"]
    unit = metric.get("unit", "")

    results = read_results("results.tsv")

    print(header(config["name"], config.get("description", "")))

    if not results:
        print(f"  {DIM}No results yet.{RESET} Run {BOLD_WHITE}autoresearch test{RESET} to verify your setup.")
        print()
        return

    # Parse metric values
    values = []
    for r in results:
        try:
            values.append(float(r.get(metric_name, "")))
        except (ValueError, TypeError):
            values.append(None)

    valid = [v for v in values if v is not None]

    if not valid:
        print(f"  {len(results)} runs, but no valid {metric_name} values found.")
        print()
        return

    best = min(valid) if direction == "lower" else max(valid)
    first = valid[0]
    latest = valid[-1]

    # Improvement from first to best
    if first != 0:
        if direction == "lower":
            improvement = ((first - best) / first) * 100
        else:
            improvement = ((best - first) / first) * 100
    else:
        improvement = 0

    # Sparkline — invert for "lower is better" so improvements go up
    spark = sparkline(values, width=20, invert=(direction == "lower"))

    # Streak
    streak = count_streak(valid, direction)

    # Summary stats
    best_str = format_value(best, unit)
    latest_str = format_value(latest, unit)

    print(f"  {DIM}Runs{RESET}         {BOLD_WHITE}{len(results)}{RESET}       {DIM}{spark}{RESET}")
    print(f"  {DIM}Best{RESET}         {BOLD_GREEN}{best_str}{RESET}")
    print(f"  {DIM}Latest{RESET}       {BOLD_WHITE}{latest_str}{RESET}")

    if len(valid) > 1:
        if improvement > 0:
            color = GREEN
        else:
            color = RED
        print(f"  {DIM}Improvement{RESET}  {color}{improvement:+.1f}%{RESET}")

    if streak >= 2:
        print(f"  {DIM}Streak{RESET}       {BOLD_YELLOW}{streak} consecutive improvements{RESET}")

    print()

    # Last 5 runs with deltas
    n = min(5, len(results))
    print(f"  {DIM}Last {n} runs:{RESET}")

    shown = results[-n:]
    shown_values = values[-n:]

    # Get the value before the shown window for first delta
    pre_idx = len(values) - n - 1
    prev_val = values[pre_idx] if pre_idx >= 0 else None

    for i, r in enumerate(shown):
        val_raw = r.get(metric_name, "?")
        status = r.get("status", "")
        desc = r.get("description", "")
        val = shown_values[i]

        # Format value
        if val is not None:
            val_str = format_value(val, unit)
            is_best = val == best
        else:
            val_str = val_raw
            is_best = False

        # Delta from previous
        delta_str = ""
        if val is not None and prev_val is not None:
            delta_str, _ = format_delta(val, prev_val, direction)
            if delta_str:
                delta_str = f" {delta_str}"

        # Color the value
        if is_best:
            val_display = f"{BOLD_GREEN}{val_str}{RESET}"
            marker = f" {BOLD_YELLOW}*{RESET}"
        else:
            val_display = f"{BOLD_WHITE}{val_str}{RESET}"
            marker = ""

        # Build line
        line = f"    {val_display}{delta_str}{marker}"
        if desc:
            line += f"  {DIM}{desc}{RESET}"

        print(line)

        if val is not None:
            prev_val = val

    print()


if __name__ == "__main__":
    main()
