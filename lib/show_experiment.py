#!/usr/bin/env python3
"""Show details of a single experiment. Stdlib only."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from graph import load, get_node
from experiment import load_experiment
from tui import BOLD, BOLD_GREEN, BOLD_WHITE, BOLD_YELLOW, DIM, RED, RESET


def main():
    if len(sys.argv) < 2:
        print("Usage: autoresearch show <commit>", file=sys.stderr)
        sys.exit(1)

    commit = sys.argv[1]

    graph = load()
    if graph is None:
        print("No graph.json found.", file=sys.stderr)
        sys.exit(1)

    node = get_node(graph, commit)
    if node is None:
        print(f"Experiment {commit} not found in graph.", file=sys.stderr)
        sys.exit(1)

    unit = graph["metric"].get("unit", "")

    # Header
    status_color = BOLD_GREEN if node["status"] == "keep" else (RED if node["status"] in ("discard", "crash") else BOLD_WHITE)
    print()
    print(f"  {BOLD_WHITE}{commit}{RESET}  {status_color}{node['status']}{RESET}  {node.get('type', '')}")
    print(f"  {DIM}Description:{RESET} {node.get('description', '')}")
    print(f"  {DIM}Metric:{RESET} {node['metric']}{unit}" if node["metric"] is not None else f"  {DIM}Metric:{RESET} pending")
    print(f"  {DIM}Branch:{RESET} {node.get('branch', '?')}")
    print(f"  {DIM}Parent:{RESET} {node.get('parent', 'none')}")
    print(f"  {DIM}Children:{RESET} {', '.join(node.get('children', [])) or 'none'}")
    print(f"  {DIM}Timestamp:{RESET} {node.get('timestamp', '?')}")

    # Annotations
    annotations = node.get("annotations", {})
    if annotations:
        print(f"  {DIM}Annotations:{RESET}")
        for k, v in annotations.items():
            print(f"    {k}: {v}")

    # Experiment data from disk
    exp = load_experiment(commit)
    if exp:
        if "diff" in exp:
            print()
            print(f"  {BOLD_WHITE}Diff:{RESET}")
            for line in exp["diff"].splitlines()[:30]:
                print(f"    {line}")
            if len(exp["diff"].splitlines()) > 30:
                print(f"    {DIM}... ({len(exp['diff'].splitlines()) - 30} more lines){RESET}")

        if "trace" in exp:
            print()
            print(f"  {BOLD_WHITE}Trace (last 20 lines):{RESET}")
            trace_lines = exp["trace"].splitlines()
            for line in trace_lines[-20:]:
                print(f"    {line}")

    print()


if __name__ == "__main__":
    main()
