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

VALID_EXTRACTORS = {"duration", "file-size", "regexp"}
VALID_RIGOR = {"light", "standard", "strict"}

# ── Scientist prompt blocks by rigor level ──────────────────────────────

SCIENTIST_LIGHT = """\
## Experiment discipline

- Log every experiment in `results.tsv` immediately after running it.
- Maintain `autoresearch.ideas.md` as a prioritized list of what to try next.
- When you discover a promising idea you won't pursue immediately, add it to the backlog with a one-line rationale.
- When an idea has been tried or is clearly bad, remove it from the backlog."""

SCIENTIST_STANDARD = """\
## Scientific method

You are a scientist running controlled experiments. Rigor matters more than speed.

### Before each experiment

Write a hypothesis in `autoresearch.md` before making any changes:

```
### Experiment N: <short title>
**Hypothesis:** <what you expect to change and why>
**Variable:** <the single thing you're changing>
**Expected effect:** <predicted direction and rough magnitude>
```

### One variable at a time

Change exactly one thing per experiment. If you want to try two ideas, run them as two separate experiments. Combining changes makes it impossible to know what worked. If you catch yourself changing multiple things, stop and split the experiment.

### After each experiment

Complete the entry in `autoresearch.md`:

```
**Result:** <metric value>
**Vs hypothesis:** <confirmed / partially confirmed / refuted>
**Interpretation:** <why did this happen? what did you learn?>
```

If the result surprises you, spend a moment understanding why before moving on. Surprises are where the best insights live.

### Ideas backlog

Maintain `autoresearch.ideas.md` as a prioritized list:

```
1. <idea> — expected impact: <high/medium/low> — rationale: <why this might work>
2. ...
```

Re-prioritize after each experiment based on what you learned. Remove ideas that have been tried. Add new ideas that emerge from results.

### Diminishing returns

After 3+ consecutive experiments with <2% improvement each, note this in `autoresearch.md` and consider:
- Are you optimizing the right thing?
- Is there a structural change that would unlock a bigger gain?
- Has this metric reached a practical floor/ceiling?

Shift strategy before grinding out marginal gains."""

SCIENTIST_STRICT = SCIENTIST_STANDARD + """

### Statistical confidence

Measurements have variance. A single run proving "improvement" might be noise.

- **Baseline**: Run the benchmark 3 times before any changes. Record all 3 values. Your baseline is the median.
- **Confirmation**: When an experiment shows improvement, run the benchmark 2 more times. Keep only if the median of 3 runs beats the baseline median.
- **Variance tracking**: If your 3 baseline runs vary by more than 10%, note this in `autoresearch.md`. High-variance metrics need more runs to establish significance.

### Control experiments

Every 5th experiment, run a control: revert to the last known-good state and re-run the benchmark. If the control doesn't reproduce the expected value (within baseline variance), something has drifted. Investigate before continuing.

### Lab notebook standard

Each experiment entry in `autoresearch.md` must include:

```
### Experiment N: <title>
**Hypothesis:** <prediction and reasoning>
**Variable:** <exactly what changed>
**Expected effect:** <direction, magnitude>
**Baseline (median of 3):** <value>
**Result (median of 3):** <value>
**Delta:** <% change>
**Vs hypothesis:** <confirmed / partially confirmed / refuted>
**Confidence:** <high — consistent across runs / medium — some variance / low — within noise>
**Interpretation:** <what you learned, implications for next experiments>
```

Do not skip fields. Incomplete entries undermine the entire log."""


def _build_extraction_block(metric):
    """Generate a bash block that extracts the METRIC line from eval output.

    When metric.extract is set, the eval command's output doesn't need to
    include a METRIC line — the extraction block handles it.
    Returns an empty string if no extractor is configured.
    """
    extract = metric.get("extract", "")
    if not extract:
        return ""

    name = metric["name"]
    parts = extract.split(None, 1)
    extractor = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if extractor == "duration":
        # macOS-portable timing using python3 (date +%s%N doesn't work on macOS)
        return (
            '_AR_START=$(python3 -c "import time; print(int(time.time()))")\n'
            '{eval_cmd}\n'
            '_AR_END=$(python3 -c "import time; print(int(time.time()))")\n'
            f'echo "METRIC {name}=$(( _AR_END - _AR_START ))"'
        )
    elif extractor == "file-size":
        if not arg:
            print("Error: file-size extractor requires a path argument, e.g. 'file-size dist/'", file=sys.stderr)
            sys.exit(1)
        return (
            '{eval_cmd}\n'
            f'echo "METRIC {name}=$(du -sk {arg} | cut -f1)"'
        )
    elif extractor == "regexp":
        if not arg:
            print("Error: regexp extractor requires a pattern argument", file=sys.stderr)
            sys.exit(1)
        # The pattern should have a capture group for the numeric value
        return (
            '{eval_cmd}\n'
            f'_AR_VAL=$(cat .autoresearch_output | python3 -c "import sys,re; m=re.search(r\'{arg}\', sys.stdin.read()); print(m.group(1) if m else \'\')")\n'
            f'echo "METRIC {name}=$_AR_VAL"'
        )
    else:
        print(f"Error: unknown extractor '{extractor}'. Valid: {', '.join(sorted(VALID_EXTRACTORS))}", file=sys.stderr)
        sys.exit(1)


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
            # Multi-line literal block — collect lines until the next
            # top-level YAML key (word: at indent 0). Lines at indent 0
            # that don't match a key pattern are still part of the block
            # (e.g. inline Python inside a shell heredoc).
            block_lines = []
            block_indent = None
            i += 1
            while i < len(lines):
                bline = lines[i]
                if bline.strip() == "":
                    block_lines.append("")
                    i += 1
                    continue
                bindent = len(bline) - len(bline.lstrip())
                # Detect block indent from first content line
                if block_indent is None and bindent > 0:
                    block_indent = bindent
                # A line at indent 0 that looks like a YAML key ends the block
                if bindent == 0 and re.match(r"^\w+:\s*", bline):
                    break
                # Strip the block indent prefix, preserving relative indentation
                if block_indent and bindent >= block_indent:
                    block_lines.append(bline[block_indent:])
                else:
                    block_lines.append(bline.strip())
                i += 1
            # Remove trailing empty lines
            while block_lines and block_lines[-1] == "":
                block_lines.pop()
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

    # Validate extract field if present
    extract = metric.get("extract", "")
    if extract:
        extractor = extract.split(None, 1)[0]
        if extractor not in VALID_EXTRACTORS:
            print(f"Error: unknown metric.extract '{extractor}'. Valid: {', '.join(sorted(VALID_EXTRACTORS))}", file=sys.stderr)
            sys.exit(1)

    # Ensure lists
    for key in ("mutable", "immutable", "constraints"):
        if isinstance(config.get(key), str):
            config[key] = [config[key]]

    # Validate and generate scientist_block from rigor level
    rigor = config.get("rigor", "standard")
    if rigor not in VALID_RIGOR:
        print(f"Error: rigor must be one of {', '.join(sorted(VALID_RIGOR))}, got '{rigor}'", file=sys.stderr)
        sys.exit(1)
    config["rigor"] = rigor

    RIGOR_BLOCKS = {
        "light": SCIENTIST_LIGHT,
        "standard": SCIENTIST_STANDARD,
        "strict": SCIENTIST_STRICT,
    }
    config["scientist_block"] = RIGOR_BLOCKS[rigor]

    # Generate extraction_block
    extraction_block = _build_extraction_block(metric)
    if extraction_block:
        # Substitute {eval_cmd} with the actual eval command
        config["extraction_block"] = extraction_block.replace("{eval_cmd}", config["eval"].rstrip())
        config["has_extractor"] = True
    else:
        config["extraction_block"] = ""
        config["has_extractor"] = False

    return config


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: parse_config.py <lab.yaml>", file=sys.stderr)
        sys.exit(1)
    config = parse_config(sys.argv[1])
    print(json.dumps(config, indent=2))
