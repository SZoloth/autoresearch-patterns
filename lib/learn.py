#!/usr/bin/env python3
"""Extract generalizable lessons from a completed autoresearch session.

Reads results.tsv and autoresearch.md, summarizes what worked and what didn't,
and appends structured skills to ~/.autoresearch/skills.md for injection into
future sessions.

Stdlib only — no pip dependencies.
"""

import re
import sys
from datetime import datetime
from pathlib import Path


def read_results(path):
    """Parse results.tsv into a list of dicts."""
    p = Path(path)
    if not p.exists():
        return []
    lines = p.read_text().strip().split("\n")
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        cols = line.split("\t")
        rows.append(dict(zip(headers, cols)))
    return rows


def extract_theory(session_path):
    """Extract the current theory.

    Tries graph.json first (v0.7+), falls back to parsing autoresearch.md (v0.6).
    """
    # Try graph.json first
    graph_path = Path(".autoresearch/graph.json")
    if graph_path.exists():
        try:
            import json
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            theory = graph.get("theory", "").strip()
            if theory:
                return theory
        except Exception:
            pass

    # Fall back to parsing autoresearch.md
    p = Path(session_path)
    if not p.exists():
        return ""
    text = p.read_text()
    match = re.search(
        r"## Current theory\s*\n(.*?)(?=\n## |\Z)",
        text,
        re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def compute_summary(results, metric_name, direction):
    """Compute session summary statistics."""
    total = len(results)
    if total == 0:
        return None

    keeps = [r for r in results if r.get("status") == "keep"]
    crashes = [r for r in results if r.get("status") == "crash"]
    keep_rate = len(keeps) / total * 100

    # Best improvement
    values = []
    for r in results:
        try:
            values.append(float(r.get(metric_name, "")))
        except (ValueError, TypeError):
            pass

    best_val = None
    baseline_val = None
    improvement = None
    if values:
        baseline_val = values[0]
        if direction == "lower":
            best_val = min(values)
            if baseline_val > 0:
                improvement = (baseline_val - best_val) / baseline_val * 100
        else:
            best_val = max(values)
            if baseline_val > 0:
                improvement = (best_val - baseline_val) / baseline_val * 100

    # Top successful experiment descriptions
    top_keeps = []
    for r in keeps[-5:]:
        desc = r.get("description", "")
        exp_type = r.get("type", "")
        if desc:
            entry = desc
            if exp_type:
                entry = f"[{exp_type}] {desc}"
            top_keeps.append(entry)

    # Per-type stats
    type_stats = {}
    for r in results:
        t = r.get("type", "other")
        if t not in type_stats:
            type_stats[t] = {"total": 0, "keeps": 0}
        type_stats[t]["total"] += 1
        if r.get("status") == "keep":
            type_stats[t]["keeps"] += 1

    return {
        "total": total,
        "keep_rate": keep_rate,
        "crash_count": len(crashes),
        "improvement": improvement,
        "best_val": best_val,
        "baseline_val": baseline_val,
        "top_keeps": top_keeps,
        "type_stats": type_stats,
    }


def format_skills(session_name, summary, theory):
    """Format session learnings as markdown skills."""
    lines = []
    lines.append(f"### {session_name} ({datetime.now().strftime('%Y-%m-%d')})")
    lines.append("")

    if summary["improvement"] is not None:
        lines.append(
            f"- {summary['total']} experiments, "
            f"{summary['keep_rate']:.0f}% keep rate, "
            f"{summary['improvement']:.1f}% improvement"
        )
    else:
        lines.append(
            f"- {summary['total']} experiments, "
            f"{summary['keep_rate']:.0f}% keep rate"
        )

    # Per-type insights
    if summary["type_stats"]:
        best_type = None
        best_rate = -1
        for t, stats in summary["type_stats"].items():
            if stats["total"] >= 3:
                rate = stats["keeps"] / stats["total"]
                if rate > best_rate:
                    best_rate = rate
                    best_type = t
        if best_type and best_rate > 0:
            lines.append(
                f"- Most productive experiment type: `{best_type}` "
                f"({best_rate * 100:.0f}% hit rate)"
            )

    # Top successful experiments
    if summary["top_keeps"]:
        lines.append("- What worked:")
        for desc in summary["top_keeps"][-3:]:
            lines.append(f"  - {desc}")

    # Theory
    if theory:
        # Take just the first 2-3 lines of theory as a condensed insight
        theory_lines = [l for l in theory.split("\n") if l.strip()][:3]
        lines.append("- Key insight: " + " ".join(theory_lines))

    lines.append("")
    return "\n".join(lines)


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "lab.yaml"

    # Read config for session name and metric info
    sys.path.insert(0, str(Path(__file__).parent))
    from parse_config import parse_config

    try:
        config = parse_config(config_path)
    except SystemExit:
        print("Error: could not parse config.", file=sys.stderr)
        sys.exit(1)

    session_name = config["name"]
    metric_name = config["metric"]["name"]
    direction = config["metric"].get("direction", "lower")

    # Read session data
    results = read_results("results.tsv")
    if not results:
        print("No experiments found in results.tsv.", file=sys.stderr)
        sys.exit(1)

    theory = extract_theory("autoresearch.md")
    summary = compute_summary(results, metric_name, direction)
    if summary is None:
        print("No results to summarize.", file=sys.stderr)
        sys.exit(1)

    skills_text = format_skills(session_name, summary, theory)

    # Write to ~/.autoresearch/skills.md
    skills_dir = Path.home() / ".autoresearch"
    skills_dir.mkdir(exist_ok=True)
    skills_path = skills_dir / "skills.md"

    # Append (or create)
    existing = ""
    if skills_path.exists():
        existing = skills_path.read_text()

    with open(skills_path, "a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(skills_text)

    print(f"Saved skills to {skills_path}")
    print()
    print(skills_text)


if __name__ == "__main__":
    main()
