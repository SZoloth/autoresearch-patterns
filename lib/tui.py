#!/usr/bin/env python3
"""Terminal UI utilities for autoresearch. Stdlib only."""

import os
import sys

# ── Colors ──────────────────────────────────────────────────────────────

_NO_COLOR = os.environ.get("NO_COLOR") is not None
_IS_TTY = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
_USE_COLOR = _IS_TTY and not _NO_COLOR


def _ansi(code):
    return f"\033[{code}m" if _USE_COLOR else ""


RESET = _ansi(0)
BOLD = _ansi(1)
DIM = _ansi(2)
GREEN = _ansi(32)
RED = _ansi(31)
YELLOW = _ansi(33)
CYAN = _ansi(36)
WHITE = _ansi(37)
BOLD_GREEN = _ansi("1;32")
BOLD_RED = _ansi("1;31")
BOLD_CYAN = _ansi("1;36")
BOLD_YELLOW = _ansi("1;33")
BOLD_WHITE = _ansi("1;37")


# ── Sparkline ───────────────────────────────────────────────────────────

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values, width=None, invert=False):
    """Render a sparkline string from a list of numeric values.

    None values are rendered as a space.
    When invert=True, lower values get taller bars (for "lower is better").
    """
    valid = [v for v in values if v is not None]
    if not valid:
        return ""

    lo, hi = min(valid), max(valid)
    span = hi - lo if hi != lo else 1

    chars = []
    for v in values:
        if v is None:
            chars.append(" ")
        else:
            idx = int((v - lo) / span * (len(SPARK_CHARS) - 1))
            if invert:
                idx = len(SPARK_CHARS) - 1 - idx
            chars.append(SPARK_CHARS[idx])

    result = "".join(chars)
    if width and len(result) > width:
        result = result[-width:]
    return result


# ── Delta formatting ────────────────────────────────────────────────────

def format_delta(current, previous, direction):
    """Format a delta between two values as colored percentage.

    Returns (delta_str, is_improvement).
    """
    if previous is None or previous == 0:
        return "", None

    pct = ((current - previous) / abs(previous)) * 100

    if direction == "lower":
        is_improvement = pct < 0
    else:
        is_improvement = pct > 0

    arrow = "↓" if pct < 0 else "↑"
    color = GREEN if is_improvement else RED

    return f"{color}{arrow}{abs(pct):.0f}%{RESET}", is_improvement


# ── Streak detection ────────────────────────────────────────────────────

def count_streak(values, direction):
    """Count consecutive improvements from the end of the values list.

    Returns 0 if the last value is not an improvement.
    """
    if len(values) < 2:
        return 0

    streak = 0
    for i in range(len(values) - 1, 0, -1):
        curr, prev = values[i], values[i - 1]
        if curr is None or prev is None:
            break
        if direction == "lower":
            improved = curr < prev
        else:
            improved = curr > prev
        if improved:
            streak += 1
        else:
            break

    return streak


# ── Value formatting ────────────────────────────────────────────────────

def format_value(val, unit=""):
    """Format a metric value with unit."""
    unit_str = f" {unit}" if unit else ""
    if isinstance(val, float) and val == int(val):
        return f"{int(val)}{unit_str}"
    if isinstance(val, float):
        return f"{val:.1f}{unit_str}"
    return f"{val}{unit_str}"


# ── Box drawing ─────────────────────────────────────────────────────────

def header(title, subtitle=""):
    """Render a styled section header."""
    lines = []
    lines.append("")
    lines.append(f"  {BOLD_CYAN}{title}{RESET}")
    if subtitle:
        lines.append(f"  {DIM}{subtitle}{RESET}")
    lines.append(f"  {DIM}{'─' * 44}{RESET}")
    return "\n".join(lines)


def banner(name, metric_name, direction, unit=""):
    """Render the init completion banner."""
    arrow = "↓" if direction == "lower" else "↑"
    unit_str = f" ({unit})" if unit else ""
    lines = []
    lines.append("")
    lines.append(f"  {BOLD_CYAN}{'━' * 44}{RESET}")
    lines.append(f"  {BOLD_WHITE}  autoresearch{RESET}")
    lines.append(f"  {BOLD_CYAN}{'━' * 44}{RESET}")
    lines.append("")
    lines.append(f"  {BOLD_WHITE}{name}{RESET}")
    lines.append(f"  {DIM}optimizing{RESET} {metric_name}{unit_str} {arrow}")
    lines.append("")
    return "\n".join(lines)


# ── Test result formatting ──────────────────────────────────────────────

def format_test_result(metric_key, metric_val, unit="", direction="lower",
                       best=None, baseline=None):
    """Format the test command result with comparison to best/baseline."""
    unit_str = f" {unit}" if unit else ""
    lines = []

    try:
        val = float(metric_val)
    except (ValueError, TypeError):
        lines.append(f"  {BOLD_WHITE}{metric_key}{RESET} = {metric_val}{unit_str}")
        return "\n".join(lines)

    val_str = format_value(val, unit)

    if best is not None:
        if direction == "lower":
            is_new_best = val < best
        else:
            is_new_best = val > best

        if is_new_best and baseline is not None and baseline != 0:
            if direction == "lower":
                total_pct = ((baseline - val) / baseline) * 100
            else:
                total_pct = ((val - baseline) / baseline) * 100
            lines.append(
                f"  {BOLD_GREEN}{metric_key} = {val_str}  "
                f"new best! ↓{total_pct:.0f}% from baseline{RESET}"
                if direction == "lower" else
                f"  {BOLD_GREEN}{metric_key} = {val_str}  "
                f"new best! ↑{total_pct:.0f}% from baseline{RESET}"
            )
        elif is_new_best:
            lines.append(f"  {BOLD_GREEN}{metric_key} = {val_str}  new best!{RESET}")
        else:
            delta_str, _ = format_delta(val, best, direction)
            best_str = format_value(best, unit)
            lines.append(
                f"  {BOLD_WHITE}{metric_key}{RESET} = {val_str}"
                f"  {DIM}(best: {best_str}){RESET} {delta_str}"
            )
    else:
        lines.append(f"  {BOLD_WHITE}{metric_key}{RESET} = {val_str}  {DIM}(baseline){RESET}")

    return "\n".join(lines)
