#!/usr/bin/env python3
"""Auto-generated scratchpad. Stdlib only — no pip dependencies.

Writes to autoresearch.md (same path as v0.6) so agents don't need to
discover a new file. Regenerated after every state mutation.
"""

import sys
from pathlib import Path

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from graph import (
    load, get_head, get_best, get_frontier, get_stats,
    find_negative_knowledge, path_to_node, indented_tree,
)
from parse_config import parse_config


def generate_scratchpad(graph, config):
    """Generate the complete scratchpad markdown from graph state."""
    metric = graph["metric"]
    stats = get_stats(graph)
    head_node = get_head(graph)
    best_node = get_best(graph)
    unit = metric.get("unit", "")
    direction = metric.get("direction", "lower")

    lines = []

    # ── Header ────────────────────────────────────────────────────
    lines.append(f"# Autoresearch: {graph['session']}")
    lines.append("")
    lines.append(f"Optimize **{metric['name']}** ({unit}, {direction} is better).")
    lines.append("")

    # ── Current position ──────────────────────────────────────────
    lines.append("## Current position")
    if head_node:
        head_metric = f"{head_node['metric']}{unit}" if head_node["metric"] is not None else "pending"
        best_metric = f"{best_node['metric']}{unit}" if best_node and best_node["metric"] is not None else "—"
        lines.append(f"- **Head:** `{head_node['commit']}` on branch `{head_node.get('branch', '?')}`")
        lines.append(f"- **Metric:** {head_metric} (best: {best_metric})")
        lines.append(f"- **Experiments:** {stats['total']} total, {stats['keeps']} kept, {stats['discards']} discarded, {stats['crashes']} crashed")
    else:
        lines.append("- No experiments yet.")
    lines.append("")

    # ── Current theory ────────────────────────────────────────────
    theory = graph.get("theory", "").strip()
    lines.append("## Current theory")
    if theory:
        lines.append(theory)
    else:
        lines.append("_No theory yet. Update via `autoresearch record keep ... --theory \"your theory\"`_")
    lines.append("")

    # ── Path to here ──────────────────────────────────────────────
    if head_node and head_node["commit"] != graph["root"]:
        head_path = path_to_node(graph, head_node["commit"])
        lines.append("## Path to here")
        lines.append("")
        lines.append("| # | Commit | Metric | Status | Description |")
        lines.append("|---|--------|--------|--------|-------------|")
        for i, commit in enumerate(head_path, 1):
            node = graph["nodes"][commit]
            m = f"{node['metric']}{unit}" if node["metric"] is not None else "pending"
            lines.append(f"| {i} | `{commit}` | {m} | {node['status']} | {node.get('description', '')} |")
        lines.append("")

    # ── What not to try ───────────────────────────────────────────
    negatives = find_negative_knowledge(graph)
    lines.append("## What not to try")
    if negatives:
        lines.append("These approaches were tested and failed. Learn from them:")
        for item in negatives[:15]:
            suffix = f" (x{item['count']})" if item["count"] > 1 else ""
            m = f"{item['metric']}{unit}" if item["metric"] is not None else "crashed"
            lines.append(f"- **{item['description']}** (`{item['commit']}`, {m}){suffix}")
    else:
        lines.append("_No failed experiments yet._")
    lines.append("")

    # ── Frontier ──────────────────────────────────────────────────
    frontier = get_frontier(graph)
    lines.append("## Frontier")
    lines.append("Leaf nodes you can fork from to try a different approach:")
    if frontier:
        lines.append("")
        lines.append("| Commit | Metric | Branch | Description |")
        lines.append("|--------|--------|--------|-------------|")
        for node in frontier[:10]:
            m = f"{node['metric']}{unit}" if node["metric"] is not None else "—"
            lines.append(f"| `{node['commit']}` | {m} | `{node.get('branch', '?')}` | {node.get('description', '')} |")
    else:
        lines.append("_No frontier nodes yet._")
    lines.append("")

    # ── Best experiments ──────────────────────────────────────────
    kept = [n for n in graph["nodes"].values() if n["status"] in ("keep", "baseline") and n["metric"] is not None]
    reverse = direction == "higher"
    kept.sort(key=lambda n: n["metric"], reverse=reverse)
    lines.append("## Best experiments")
    if kept:
        for i, node in enumerate(kept[:5], 1):
            lines.append(f"{i}. `{node['commit']}` — {node['metric']}{unit} — {node.get('description', '')}")
    else:
        lines.append("_No completed experiments yet._")
    lines.append("")

    # ── Statistics ────────────────────────────────────────────────
    lines.append("## Statistics")
    if stats["total"] > 0:
        lines.append(f"- **Keep rate:** {stats['keep_rate']:.0f}% ({stats['keeps']}/{stats['total'] - stats['baselines']} experiments)")
        if stats["improvement"] is not None:
            lines.append(f"- **Best improvement:** {stats['improvement']:.1f}% from baseline")
        if stats["type_stats"]:
            lines.append("- **By type:**")
            for t, s in sorted(stats["type_stats"].items()):
                rate = (s["keeps"] / s["total"] * 100) if s["total"] > 0 else 0
                lines.append(f"  - {t}: {s['keeps']}/{s['total']} ({rate:.0f}%)")
    else:
        lines.append("_No experiments yet._")
    lines.append("")

    # ── Ideas backlog ─────────────────────────────────────────────
    ideas_path = Path("autoresearch.ideas.md")
    lines.append("## Ideas backlog")
    if ideas_path.exists():
        content = ideas_path.read_text(encoding="utf-8").strip()
        if content:
            lines.append(content)
        else:
            lines.append("_Empty. Add ideas as you discover them._")
    else:
        lines.append("_No ideas file. Create `autoresearch.ideas.md` to track ideas._")
    lines.append("")

    return "\n".join(lines)


def write_scratchpad(graph, config=None, path="autoresearch.md"):
    """Generate and write scratchpad to disk."""
    if config is None:
        try:
            config = parse_config("lab.yaml")
        except (SystemExit, Exception):
            config = {}
    content = generate_scratchpad(graph, config)
    Path(path).write_text(content, encoding="utf-8")
    return content


if __name__ == "__main__":
    graph = load()
    if graph is None:
        print("No graph.json found. Run 'autoresearch init' first.", file=sys.stderr)
        sys.exit(1)
    print(write_scratchpad(graph))
