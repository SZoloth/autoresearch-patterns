#!/usr/bin/env python3
"""Migrate a v0.6 session to v0.7 tree format. Stdlib only.

Reads results.tsv + git log, builds graph.json, creates ghost nodes for
discarded experiments (erased by git reset in v0.6), re-renders program.md,
and regenerates the scratchpad.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from graph import init_graph, add_node, update_best, save, utc_now
from scratchpad import write_scratchpad


def read_results_tsv():
    """Parse results.tsv into list of dicts."""
    path = Path("results.tsv")
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
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


def get_git_log():
    """Get commit hashes and messages from git log."""
    result = subprocess.run(
        ["git", "log", "--oneline", "--reverse"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return []
    commits = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if parts:
            commits.append({
                "hash": parts[0][:7],
                "message": parts[1] if len(parts) > 1 else "",
            })
    return commits


def get_current_branch():
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def get_head_commit():
    result = subprocess.run(
        ["git", "rev-parse", "--short=7", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def parse_config_for_migration():
    """Read lab.yaml for session name and metric info."""
    try:
        from parse_config import parse_config
        return parse_config("lab.yaml")
    except (SystemExit, Exception):
        return None


def regenerate_program_md(config):
    """Re-render program.md from current templates."""
    try:
        from render import render_file
        # Find the autoresearch installation
        script_dir = Path(__file__).parent.parent
        template = script_dir / "templates" / "program.md.tmpl"
        if template.exists():
            content = render_file(str(template), config)
            Path("program.md").write_text(content, encoding="utf-8")
            return True
    except Exception as e:
        print(f"Warning: could not regenerate program.md: {e}", file=sys.stderr)
    return False


def main():
    # Check preconditions
    if Path(".autoresearch/graph.json").exists():
        print("graph.json already exists. Migration not needed.", file=sys.stderr)
        print("  To force re-migration, delete .autoresearch/ first.", file=sys.stderr)
        sys.exit(1)

    results = read_results_tsv()
    if not results:
        print("No results.tsv found or it's empty. Nothing to migrate.", file=sys.stderr)
        sys.exit(1)

    config = parse_config_for_migration()
    if config is None:
        print("Warning: could not read lab.yaml. Using defaults.", file=sys.stderr)
        config = {
            "name": "migrated-session",
            "metric": {"name": "metric", "direction": "lower", "unit": ""},
        }

    git_log = get_git_log()
    branch = get_current_branch()
    metric_config = config.get("metric", {})
    metric_name = metric_config.get("name", "metric")

    # Build a set of existing commit hashes for lookup
    git_hashes = {c["hash"] for c in git_log}

    # Find the init commit (first commit on the autoresearch branch)
    # Use the first commit in git log as root
    root_commit = git_log[0]["hash"] if git_log else get_head_commit()
    if root_commit is None:
        print("Error: no git commits found.", file=sys.stderr)
        sys.exit(1)

    # Initialize graph
    graph = init_graph(config["name"], metric_config, root_commit, branch)

    # Process the first result as baseline
    first = results[0]
    try:
        baseline_metric = float(first.get(metric_name, 0))
    except (ValueError, TypeError):
        baseline_metric = 0
    graph["nodes"][root_commit]["metric"] = baseline_metric
    graph["nodes"][root_commit]["status"] = "baseline"
    graph["nodes"][root_commit]["description"] = first.get("description", "baseline")

    # Process remaining results
    parent = root_commit
    ghost_count = 0

    for row in results[1:]:
        commit = row.get("commit", "")[:7]
        try:
            metric_val = float(row.get(metric_name, 0))
        except (ValueError, TypeError):
            metric_val = 0

        status = row.get("status", "discard")
        exp_type = row.get("type", "other")
        description = row.get("description", "")

        # Map v0.6 statuses
        if status == "keep":
            graph_status = "keep"
        elif status == "crash":
            graph_status = "crash"
        else:
            graph_status = "discard"

        # Check if commit exists in git
        if commit and commit in git_hashes and commit not in graph["nodes"]:
            add_node(graph, commit, parent, metric_val, graph_status,
                     exp_type, description, branch)
            if graph_status == "keep":
                parent = commit
        else:
            # Ghost node — commit was erased by git reset in v0.6
            ghost_id = f"ghost_{ghost_count:03d}"
            ghost_count += 1
            if ghost_id not in graph["nodes"]:
                add_node(graph, ghost_id, parent, metric_val, graph_status,
                         exp_type, description, branch)
                graph["nodes"][ghost_id]["annotations"]["ghost"] = "true"
                graph["nodes"][ghost_id]["annotations"]["original_commit"] = commit

    # Set head to the last keep
    for commit in reversed(list(graph["nodes"].keys())):
        node = graph["nodes"][commit]
        if node["status"] == "keep" and not node.get("annotations", {}).get("ghost"):
            graph["head"] = commit
            break

    update_best(graph)

    # Create directories
    Path(".autoresearch/experiments").mkdir(parents=True, exist_ok=True)

    # Save graph
    save(graph)

    # Regenerate scratchpad
    write_scratchpad(graph, config)

    # Re-render program.md with current templates
    regenerated = regenerate_program_md(config)

    # Summary
    nodes = graph["nodes"]
    total = len(nodes)
    keeps = sum(1 for n in nodes.values() if n["status"] == "keep")
    discards = sum(1 for n in nodes.values() if n["status"] == "discard")
    ghosts = sum(1 for n in nodes.values() if n.get("annotations", {}).get("ghost"))

    print(f"Migration complete:")
    print(f"  {total} nodes ({keeps} keeps, {discards} discards, {ghosts} ghost nodes)")
    print(f"  Head: {graph['head']}")
    print(f"  Best: {graph['best']}")
    print(f"  Graph saved to .autoresearch/graph.json")
    if regenerated:
        print(f"  program.md regenerated with v0.7 tree instructions")
    else:
        print(f"  Warning: program.md not regenerated (restart agent to pick up v0.7)")
    print(f"  Scratchpad written to autoresearch.md")


if __name__ == "__main__":
    main()
