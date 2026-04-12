#!/usr/bin/env python3
"""Display the experiment tree. Stdlib only."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from graph import load, indented_tree, get_stats
from tui import BOLD, BOLD_GREEN, BOLD_WHITE, BOLD_YELLOW, DIM, RESET


def main():
    graph = load()
    if graph is None:
        print("No graph.json found. Run 'autoresearch init' first.", file=sys.stderr)
        sys.exit(1)

    stats = get_stats(graph)
    metric = graph["metric"]
    unit = metric.get("unit", "")

    print()
    print(f"  {BOLD_WHITE}{graph['session']}{RESET}")
    if stats["best_metric"] is not None:
        print(f"  {DIM}Best:{RESET} {BOLD_GREEN}{stats['best_metric']}{unit}{RESET}  "
              f"{DIM}Experiments:{RESET} {stats['total']}  "
              f"{DIM}Keeps:{RESET} {stats['keeps']}  "
              f"{DIM}Discards:{RESET} {stats['discards']}")
    print()
    print(indented_tree(graph))
    print()


if __name__ == "__main__":
    main()
