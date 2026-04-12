#!/usr/bin/env python3
"""Experiment tree operations. Stdlib only — no pip dependencies.

The graph is a flat dict of nodes keyed by short commit hash, with parent/children
pointers forming a tree. All functions are pure (operate on the dict) except
load/save which handle JSON I/O with atomic writes.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

GRAPH_PATH = ".autoresearch/graph.json"


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── I/O ──────────────────────────────────────────────────────────────

def load(path=GRAPH_PATH):
    """Load graph from disk. Returns None if file doesn't exist."""
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save(graph, path=GRAPH_PATH):
    """Atomically write graph to disk (write to .tmp, rename)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(graph, f, indent=2, sort_keys=False)
            f.write("\n")
        os.replace(tmp, str(p))
    except Exception:
        os.unlink(tmp)
        raise


# ── Graph creation ───────────────────────────────────────────────────

def init_graph(session, metric, root_commit, branch):
    """Create a new graph with a pending root node.

    Args:
        session: session name (e.g. "optimize-test-speed")
        metric: dict with name, direction, unit
        root_commit: short commit hash of the init commit
        branch: git branch name
    """
    return {
        "version": 1,
        "session": session,
        "metric": {
            "name": metric.get("name", ""),
            "direction": metric.get("direction", "lower"),
            "unit": metric.get("unit", ""),
        },
        "root": root_commit,
        "head": root_commit,
        "best": root_commit,
        "next_fork": 1,
        "theory": "",
        "nodes": {
            root_commit: {
                "commit": root_commit,
                "parent": None,
                "children": [],
                "metric": None,
                "status": "pending",
                "type": "baseline",
                "description": "baseline measurement",
                "branch": branch,
                "timestamp": utc_now(),
                "annotations": {},
            }
        },
    }


# ── Node operations ──────────────────────────────────────────────────

def add_node(graph, commit, parent, metric, status, exp_type, description, branch):
    """Add an experiment node to the graph. Returns the updated graph."""
    if commit in graph["nodes"]:
        raise ValueError(f"Node {commit} already exists in graph")
    if parent not in graph["nodes"]:
        raise ValueError(f"Parent {parent} not found in graph")

    node = {
        "commit": commit,
        "parent": parent,
        "children": [],
        "metric": metric,
        "status": status,
        "type": exp_type,
        "description": description,
        "branch": branch,
        "timestamp": utc_now(),
        "annotations": {},
    }
    graph["nodes"][commit] = node
    graph["nodes"][parent]["children"].append(commit)
    return graph


def update_node_metric(graph, commit, metric, status):
    """Update a node's metric value and status (used by test for baseline)."""
    if commit not in graph["nodes"]:
        raise ValueError(f"Node {commit} not found in graph")
    graph["nodes"][commit]["metric"] = metric
    graph["nodes"][commit]["status"] = status
    return graph


def set_head(graph, commit):
    """Move the head pointer to a different node."""
    if commit not in graph["nodes"]:
        raise ValueError(f"Node {commit} not found in graph")
    graph["head"] = commit
    return graph


def update_best(graph):
    """Recompute the global best node based on metric + direction."""
    direction = graph["metric"]["direction"]
    best_commit = None
    best_metric = None

    for commit, node in graph["nodes"].items():
        if node["status"] not in ("keep", "baseline"):
            continue
        if node["metric"] is None:
            continue
        if best_metric is None:
            best_commit = commit
            best_metric = node["metric"]
        elif direction == "lower" and node["metric"] < best_metric:
            best_commit = commit
            best_metric = node["metric"]
        elif direction == "higher" and node["metric"] > best_metric:
            best_commit = commit
            best_metric = node["metric"]

    if best_commit is not None:
        graph["best"] = best_commit
    return graph


def update_theory(graph, theory_text):
    """Set the theory field."""
    graph["theory"] = theory_text
    return graph


def annotate(graph, commit, key, value):
    """Add/update an annotation on a node."""
    if commit not in graph["nodes"]:
        raise ValueError(f"Node {commit} not found in graph")
    graph["nodes"][commit]["annotations"][key] = value
    return graph


# ── Tree queries ─────────────────────────────────────────────────────

def get_node(graph, commit):
    """Get a node by commit hash. Returns None if not found."""
    return graph["nodes"].get(commit)


def get_head(graph):
    """Get the current head node."""
    return graph["nodes"].get(graph.get("head"))


def get_best(graph):
    """Get the global best node."""
    return graph["nodes"].get(graph.get("best"))


def path_to_node(graph, target):
    """Return the chain of commit hashes from root to target."""
    if target not in graph["nodes"]:
        return []
    chain = []
    current = target
    while current is not None:
        chain.append(current)
        current = graph["nodes"][current].get("parent")
    chain.reverse()
    return chain


def get_frontier(graph):
    """Return leaf nodes with status keep/baseline, sorted by metric (best first).

    A frontier node is a kept/baseline node with no kept children —
    meaning it's a viable fork point for new experiments.
    """
    direction = graph["metric"]["direction"]
    frontier = []

    for commit, node in graph["nodes"].items():
        if node["status"] not in ("keep", "baseline"):
            continue
        if node["metric"] is None:
            continue
        # Check if any child is also kept (if so, this isn't a leaf)
        has_kept_child = any(
            graph["nodes"].get(c, {}).get("status") in ("keep", "baseline")
            for c in node.get("children", [])
        )
        if not has_kept_child:
            frontier.append(node)

    reverse = direction == "higher"
    frontier.sort(key=lambda n: n["metric"] if n["metric"] is not None else 0, reverse=reverse)
    return frontier


def find_negative_knowledge(graph):
    """Return discarded/crashed nodes — 'what not to try'.

    Deduplicates by normalized description text. Returns list of dicts:
    [{description, status, metric, commit, count}]
    """
    seen = {}
    for node in graph["nodes"].values():
        if node["status"] not in ("discard", "crash"):
            continue
        key = " ".join(node.get("description", "").lower().split())
        if not key:
            continue
        if key in seen:
            seen[key]["count"] += 1
        else:
            seen[key] = {
                "description": node["description"],
                "status": node["status"],
                "metric": node["metric"],
                "commit": node["commit"],
                "count": 1,
            }

    return sorted(seen.values(), key=lambda x: -x["count"])


def get_stats(graph):
    """Compute session statistics from the graph."""
    nodes = [n for n in graph["nodes"].values() if n["status"] != "pending"]
    total = len(nodes)
    keeps = sum(1 for n in nodes if n["status"] == "keep")
    discards = sum(1 for n in nodes if n["status"] == "discard")
    crashes = sum(1 for n in nodes if n["status"] == "crash")
    baselines = sum(1 for n in nodes if n["status"] == "baseline")

    # Per-type breakdown
    type_stats = {}
    for n in nodes:
        if n["status"] == "baseline":
            continue
        t = n.get("type", "other")
        if t not in type_stats:
            type_stats[t] = {"total": 0, "keeps": 0}
        type_stats[t]["total"] += 1
        if n["status"] == "keep":
            type_stats[t]["keeps"] += 1

    best_node = get_best(graph)
    best_metric = best_node["metric"] if best_node else None

    # Baseline metric
    root_node = graph["nodes"].get(graph["root"])
    baseline_metric = root_node["metric"] if root_node else None

    # Improvement
    improvement = None
    direction = graph["metric"]["direction"]
    if best_metric is not None and baseline_metric is not None and baseline_metric != 0:
        if direction == "lower":
            improvement = (baseline_metric - best_metric) / baseline_metric * 100
        else:
            improvement = (best_metric - baseline_metric) / baseline_metric * 100

    return {
        "total": total,
        "keeps": keeps,
        "discards": discards,
        "crashes": crashes,
        "baselines": baselines,
        "keep_rate": (keeps / (total - baselines) * 100) if (total - baselines) > 0 else 0,
        "type_stats": type_stats,
        "best_metric": best_metric,
        "baseline_metric": baseline_metric,
        "improvement": improvement,
    }


# ── Display ──────────────────────────────────────────────────────────

def indented_tree(graph):
    """Render the tree as a depth-based indented list.

    Example output:
      abc1234  45s  baseline  baseline measurement
        bbb2222  38s  keep  parallelize fixtures  <- head
        ccc3333  48s  discard  8 worker threads
          ddd4444  31s  keep  connection pool  * best
    """
    unit = graph["metric"].get("unit", "")
    head = graph.get("head")
    best = graph.get("best")
    lines = []

    def walk(commit, depth=0):
        node = graph["nodes"].get(commit)
        if not node:
            return
        indent = "  " * (depth + 1)
        metric_str = f"{node['metric']}{unit}" if node["metric"] is not None else "pending"
        desc = node.get("description", "")
        markers = []
        if commit == head:
            markers.append("<- head")
        if commit == best and node["status"] != "pending":
            markers.append("* best")
        marker_str = "  " + "  ".join(markers) if markers else ""
        lines.append(f"{indent}{commit}  {metric_str}  {node['status']}  {desc}{marker_str}")
        for child in sorted(node.get("children", [])):
            walk(child, depth + 1)

    walk(graph["root"])
    return "\n".join(lines)


# ── Backwards compat ─────────────────────────────────────────────────

def to_results_tsv(graph):
    """Derive results.tsv content from graph (for recovery/migration only).

    Walks all nodes in timestamp order and outputs rows matching the v0.6 format:
    commit\\tmetric_name\\tstatus\\ttype\\tdescription
    """
    metric_name = graph["metric"]["name"]
    header = f"commit\t{metric_name}\tstatus\ttype\tdescription"

    # Map graph statuses to results.tsv statuses
    status_map = {"keep": "keep", "discard": "discard", "crash": "crash", "baseline": "keep"}

    nodes = sorted(
        [n for n in graph["nodes"].values() if n["status"] not in ("pending", "unknown")],
        key=lambda n: n.get("timestamp", ""),
    )

    rows = [header]
    for node in nodes:
        tsv_status = status_map.get(node["status"], node["status"])
        metric_val = node["metric"] if node["metric"] is not None else 0
        rows.append(
            f"{node['commit']}\t{metric_val}\t{tsv_status}\t{node.get('type', 'other')}\t{node.get('description', '')}"
        )

    return "\n".join(rows) + "\n"


# ── Fork helpers ─────────────────────────────────────────────────────

def allocate_fork_id(graph):
    """Increment and return the next fork number."""
    fork_id = graph.get("next_fork", 1)
    graph["next_fork"] = fork_id + 1
    return fork_id
