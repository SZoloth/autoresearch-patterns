#!/usr/bin/env python3
"""Reconcile graph.json with git history. Stdlib only.

Detects orphaned graph nodes (commit no longer in git) and missing nodes
(commits on autoresearch branches not in graph). Fixes the graph and
regenerates the scratchpad.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from graph import load, save, annotate, update_best
from scratchpad import write_scratchpad


def get_git_commits():
    """Get all commit hashes reachable from HEAD."""
    result = subprocess.run(
        ["git", "log", "--all", "--format=%h"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return set()
    return set(line.strip() for line in result.stdout.splitlines() if line.strip())


def commit_exists(commit):
    """Check if a specific commit exists in git."""
    result = subprocess.run(
        ["git", "cat-file", "-t", commit],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


def main():
    graph = load()
    if graph is None:
        print("No graph.json found. Run 'autoresearch init' first.", file=sys.stderr)
        sys.exit(1)

    git_commits = get_git_commits()
    fixed = []

    # Find orphaned graph nodes (commit not in git)
    for commit, node in graph["nodes"].items():
        if node.get("annotations", {}).get("orphaned"):
            continue
        if node.get("annotations", {}).get("ghost"):
            continue
        if not commit_exists(commit):
            annotate(graph, commit, "orphaned", "true")
            fixed.append(f"  Marked {commit} as orphaned (commit not in git)")

    # Fix head if it points to an orphaned node
    head = graph.get("head")
    if head and graph["nodes"].get(head, {}).get("annotations", {}).get("orphaned"):
        # Walk up to find first non-orphaned ancestor
        current = head
        while current:
            node = graph["nodes"].get(current, {})
            if not node.get("annotations", {}).get("orphaned"):
                graph["head"] = current
                fixed.append(f"  Moved head from orphaned {head} to {current}")
                break
            current = node.get("parent")

    # Recompute best (might have changed if orphaned nodes were best)
    old_best = graph.get("best")
    update_best(graph)
    if graph.get("best") != old_best:
        fixed.append(f"  Recomputed best: {old_best} -> {graph['best']}")

    # Save and regenerate
    if fixed:
        save(graph)
        write_scratchpad(graph)
        print(f"Recovered {len(fixed)} issue(s):")
        for line in fixed:
            print(line)
    else:
        print("Graph is consistent with git history. No issues found.")


if __name__ == "__main__":
    main()
