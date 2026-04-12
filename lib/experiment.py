#!/usr/bin/env python3
"""Per-experiment storage. Stdlib only — no pip dependencies.

Each experiment gets a directory under .autoresearch/experiments/<commit>/
with result.json (always) and optionally diff.patch + trace.log (keeps only).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

EXPERIMENTS_DIR = ".autoresearch/experiments"


def _exp_dir(commit):
    return Path(EXPERIMENTS_DIR) / commit


def save_experiment(commit, metric, status, exp_type, description, save_traces=False):
    """Save experiment data to .autoresearch/experiments/<commit>/.

    Args:
        commit: short commit hash
        metric: numeric metric value
        status: keep, discard, crash, baseline
        exp_type: architecture, parameter, etc.
        description: short description
        save_traces: if True, capture diff.patch and trace.log (for keeps)
    """
    d = _exp_dir(commit)
    d.mkdir(parents=True, exist_ok=True)

    result = {
        "commit": commit,
        "metric": metric,
        "status": status,
        "type": exp_type,
        "description": description,
    }
    (d / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )

    if save_traces:
        diff = capture_diff()
        if diff:
            (d / "diff.patch").write_text(diff, encoding="utf-8")
        trace = capture_trace()
        if trace:
            (d / "trace.log").write_text(trace, encoding="utf-8")


def load_experiment(commit):
    """Load experiment data from directory. Returns None if not found."""
    result_path = _exp_dir(commit) / "result.json"
    if not result_path.exists():
        return None
    data = json.loads(result_path.read_text(encoding="utf-8"))

    diff_path = _exp_dir(commit) / "diff.patch"
    if diff_path.exists():
        data["diff"] = diff_path.read_text(encoding="utf-8")

    trace_path = _exp_dir(commit) / "trace.log"
    if trace_path.exists():
        data["trace"] = trace_path.read_text(encoding="utf-8")

    return data


def capture_diff():
    """Capture git diff of the most recent commit vs its parent."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def capture_trace():
    """Read last_run.log if it exists."""
    for path in ("last_run.log", "run.log"):
        p = Path(path)
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                pass
    return ""
