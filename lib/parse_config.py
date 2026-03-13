#!/usr/bin/env python3
"""Parse lab.yaml config files. Stdlib only — no pip dependencies."""

import json
import re
import sys
from pathlib import Path

DEFAULTS = {
    "description": "",
    "immutable": [],
    "constraints": [],
    "timeout": 300,
}

REQUIRED = ["name", "metric", "eval", "mutable"]


def parse_yaml_simple(text):
    """Minimal YAML parser for flat and simple nested structures.

    Handles: scalars, lists (- item), one level of mapping nesting,
    multi-line literal blocks (|).
    Does NOT handle: anchors, tags, flow style, folded blocks (>).
    """
    result = {}
    current_key = None
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        indent = len(line) - len(line.lstrip())

        # Indented list item under a top-level key
        if indent > 0 and stripped.startswith("- "):
            value = stripped[2:].strip()
            if current_key and isinstance(result.get(current_key), list):
                result[current_key].append(value)
            i += 1
            continue

        # Indented key:value under a top-level key (nested mapping)
        if indent > 0 and current_key:
            match = re.match(r"^(\w+):\s*(.*)", stripped)
            if match:
                subkey = match.group(1)
                subval = match.group(2).strip()
                if not isinstance(result.get(current_key), dict):
                    result[current_key] = {}
                result[current_key][subkey] = _cast(subval) if subval else ""
            i += 1
            continue

        # Top-level key: value
        match = re.match(r"^(\w+):\s*(.*)", stripped)
        if not match:
            i += 1
            continue

        key = match.group(1)
        value = match.group(2).strip()

        if value == "|":
            # Multi-line literal block — collect indented lines
            block_lines = []
            i += 1
            while i < len(lines):
                bline = lines[i]
                if bline.strip() == "":
                    block_lines.append("")
                    i += 1
                    continue
                bindent = len(bline) - len(bline.lstrip())
                if bindent > 0:
                    block_lines.append(bline.strip())
                    i += 1
                else:
                    break
            result[key] = "\n".join(block_lines)
            current_key = key
            continue
        elif value == "":
            # Collect children — could be list or mapping, determined by first child
            result[key] = None  # placeholder
            current_key = key
            # Peek ahead to determine type
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith("#")):
                j += 1
            if j < len(lines) and lines[j].strip().startswith("- "):
                result[key] = []
            else:
                result[key] = {}
        else:
            result[key] = _cast(value)
            current_key = key

        i += 1

    return result


def _cast(value):
    """Cast string values to appropriate Python types."""
    # Strip surrounding quotes
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def parse_config(path):
    """Parse a lab.yaml file and return validated config dict."""
    text = Path(path).read_text()

    # Try stdlib yaml first (available in Python 3.x if PyYAML is installed)
    try:
        import yaml
        config = yaml.safe_load(text)
    except ImportError:
        config = parse_yaml_simple(text)

    # Apply defaults
    for key, default in DEFAULTS.items():
        if key not in config:
            config[key] = default

    # Validate required fields
    missing = [k for k in REQUIRED if k not in config or not config[k]]
    if missing:
        print(f"Error: missing required fields in lab.yaml: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # Validate metric structure
    metric = config.get("metric", {})
    if not isinstance(metric, dict):
        print("Error: 'metric' must be a mapping with 'name', 'unit', 'direction'", file=sys.stderr)
        sys.exit(1)
    if "name" not in metric:
        print("Error: metric.name is required", file=sys.stderr)
        sys.exit(1)
    if "direction" not in metric:
        metric["direction"] = "lower"
    if metric["direction"] not in ("lower", "higher"):
        print(f"Error: metric.direction must be 'lower' or 'higher', got '{metric['direction']}'", file=sys.stderr)
        sys.exit(1)
    if "unit" not in metric:
        metric["unit"] = ""

    # Ensure lists
    for key in ("mutable", "immutable", "constraints"):
        if isinstance(config.get(key), str):
            config[key] = [config[key]]

    return config


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: parse_config.py <lab.yaml>", file=sys.stderr)
        sys.exit(1)
    config = parse_config(sys.argv[1])
    print(json.dumps(config, indent=2))
