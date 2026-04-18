#!/usr/bin/env python3
"""Fork from any committed node in the experiment tree. Stdlib only.

Usage:
    autoresearch fork <commit>
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from graph import load, save, set_head, allocate_fork_id
from scratchpad import write_scratchpad


def check_dirty_tree():
    """Abort if working tree has uncommitted changes."""
    result = subprocess.run(
        ["git", "diff-index", "--quiet", "HEAD", "--"],
        check=False,
    )
    if result.returncode != 0:
        print("Error: working tree has uncommitted changes.", file=sys.stderr)
        print("  Commit or stash your changes before forking.", file=sys.stderr)
        sys.exit(1)


def commit_exists_in_git(commit):
    """Check if a commit hash exists in git."""
    result = subprocess.run(
        ["git", "cat-file", "-t", commit],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "commit"


def main():
    if len(sys.argv) < 2:
        print("Usage: autoresearch fork <commit>", file=sys.stderr)
        sys.exit(1)

    target = sys.argv[1]

    # Load graph
    graph = load()
    if graph is None:
        print("Error: no graph.json found. Run 'autoresearch init' first.", file=sys.stderr)
        sys.exit(1)

    # Validate commit in graph
    if target not in graph["nodes"]:
        print(f"Error: commit {target} not found in the experiment tree.", file=sys.stderr)
        print("  Run 'autoresearch tree' to see available nodes.", file=sys.stderr)
        sys.exit(1)

    node = graph["nodes"][target]
    if node["status"] not in ("keep", "baseline"):
        print(f"Error: can only fork from keep/baseline nodes (this is {node['status']}).", file=sys.stderr)
        sys.exit(1)

    # Validate commit in git
    if not commit_exists_in_git(target):
        print(f"Error: commit {target} not found in git history.", file=sys.stderr)
        print("  Run 'autoresearch recover' to reconcile graph with git.", file=sys.stderr)
        sys.exit(1)

    # Check dirty tree
    check_dirty_tree()

    # Create fork branch
    fork_id = allocate_fork_id(graph)
    session = graph["session"]
    branch_name = f"autoresearch/{session}/fork-{fork_id}"

    # Handle branch name collision
    while True:
        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            check=False,
        )
        if result.returncode != 0:
            break
        fork_id = allocate_fork_id(graph)
        branch_name = f"autoresearch/{session}/fork-{fork_id}"

    result = subprocess.run(
        ["git", "checkout", "-b", branch_name, target],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(f"Error: git checkout failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    # Update graph
    set_head(graph, target)
    write_scratchpad(graph)
    save(graph)

    print(f"Forked to {branch_name} from {target}")
    print(f"  Head is now at {target} ({node.get('description', '')})")
    print(f"  Metric: {node['metric']}{graph['metric'].get('unit', '')}")


if __name__ == "__main__":
    main()
