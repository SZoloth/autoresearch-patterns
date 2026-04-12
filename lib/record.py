#!/usr/bin/env python3
"""Record an experiment result into the graph. Stdlib only.

Usage:
    autoresearch record <status> <value> [--type T] [--description D] [--theory "..."]

Where status is: keep, discard, crash
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from graph import (
    load, save, add_node, set_head, update_best, update_theory,
    allocate_fork_id,
)
from experiment import save_experiment, capture_diff, capture_trace
from scratchpad import write_scratchpad


def get_head_commit():
    """Get the short commit hash of HEAD."""
    result = subprocess.run(
        ["git", "rev-parse", "--short=7", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print("Error: not inside a git repository or no commits.", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def get_current_branch():
    """Get the current git branch name."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def append_results_tsv(commit, metric_name, metric_value, status, exp_type, description):
    """Append a row to results.tsv (backwards compat)."""
    tsv_path = Path("results.tsv")
    if not tsv_path.exists():
        return

    # Map statuses
    status_map = {"keep": "keep", "discard": "discard", "crash": "crash"}
    tsv_status = status_map.get(status, status)
    row = f"{commit}\t{metric_value}\t{tsv_status}\t{exp_type}\t{description}\n"

    with open(tsv_path, "a", encoding="utf-8") as f:
        f.write(row)


def auto_fork_from_parent(graph, parent_commit):
    """Create a new branch from the parent commit (for discard/crash).

    Returns the new branch name.
    """
    fork_id = allocate_fork_id(graph)
    session = graph["session"]
    branch_name = f"autoresearch/{session}/fork-{fork_id}"

    # Check if branch already exists, increment if so
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
        ["git", "checkout", "-b", branch_name, parent_commit],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(f"Warning: could not create fork branch: {result.stderr.strip()}", file=sys.stderr)
        return None
    return branch_name


def main():
    parser = argparse.ArgumentParser(
        prog="autoresearch record",
        description="Record an experiment result into the graph.",
    )
    parser.add_argument("status", choices=["keep", "discard", "crash"],
                        help="Experiment outcome")
    parser.add_argument("value", type=float,
                        help="Metric value")
    parser.add_argument("--type", dest="exp_type", default="other",
                        choices=["architecture", "parameter", "simplification",
                                 "algorithmic", "infrastructure", "other"],
                        help="Experiment category")
    parser.add_argument("--description", "-d", default="",
                        help="Short description of what was tried")
    parser.add_argument("--theory", default=None,
                        help="Update the current theory about the system")
    args = parser.parse_args()

    # Load graph
    graph = load()
    if graph is None:
        print("Error: no graph.json found. Run 'autoresearch init' first.", file=sys.stderr)
        sys.exit(1)

    # Get current commit
    commit = get_head_commit()

    # Reject if already recorded
    if commit in graph["nodes"]:
        print(f"Error: commit {commit} is already in the graph. Did you forget to commit first?", file=sys.stderr)
        sys.exit(1)

    # Determine parent (current head in graph)
    parent = graph["head"]
    branch = get_current_branch()
    metric_name = graph["metric"]["name"]

    # Add node to graph
    add_node(graph, commit, parent, args.value, args.status,
             args.exp_type, args.description, branch)

    # Save experiment data
    save_traces = args.status == "keep"
    save_experiment(commit, args.value, args.status, args.exp_type,
                    args.description, save_traces=save_traces)

    # Handle status-specific logic
    if args.status == "keep":
        set_head(graph, commit)
        update_best(graph)
        print(f"KEEP {commit} {metric_name}={args.value} — {args.description}")

    elif args.status in ("discard", "crash"):
        # Auto-fork from parent to continue experimenting
        new_branch = auto_fork_from_parent(graph, parent)
        set_head(graph, parent)
        label = "DISCARD" if args.status == "discard" else "CRASH"
        print(f"{label} {commit} {metric_name}={args.value} — {args.description}")
        if new_branch:
            print(f"  Forked to {new_branch} from {parent}")

    # Update theory if provided
    if args.theory:
        update_theory(graph, args.theory)

    # Append to results.tsv (backwards compat)
    append_results_tsv(commit, metric_name, args.value, args.status,
                       args.exp_type, args.description)

    # Regenerate scratchpad
    write_scratchpad(graph)

    # Save graph
    save(graph)


if __name__ == "__main__":
    main()
