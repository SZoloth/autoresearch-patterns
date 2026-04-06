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

VALID_EXTRACTORS = {"duration", "file-size", "regexp", "composite"}
VALID_RIGOR = {"light", "standard", "strict", "adaptive"}

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
**Root cause:** <what is the causal mechanism? why did this specific change produce this specific effect?>
**Learnings:** <what does this tell you about the system that you didn't know before?>
```

Don't just note whether your hypothesis was right — explain *why* the result happened. Trace the causal chain from your code change to the metric movement. "It got faster" is not analysis. "Removing the N+1 query eliminated 200ms of serial database calls per run" is.

If the result surprises you, the root cause matters even more. Surprises mean your mental model of the system is wrong. Fix the model before running the next experiment.

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

# ── Strategic checkpoint block ────────────────────────────────────────

CHECKPOINT_BLOCK = """\
## Strategic checkpoints

Every {{checkpoint_interval}} experiments (count rows in `results.tsv` since your last strategic review), **pause the loop** and run the protocol below before your next hypothesis. This is mandatory, not optional.

### 1. Compute meta-metrics

Analyze the last {{checkpoint_interval}} rows of `results.tsv`:

- **Hit rate** — what fraction were `keep`? (keeps ÷ total)
- **Velocity** — compare the best metric value in this batch to the best in the batch before it. Is improvement accelerating, steady, or stalling?
- **Diversity** — look at the `description` column. Are you varying your approach (different files, different strategies) or grinding the same angle?
- **Crash rate** — what fraction were `crash`?
- **Per-type success rates** — group experiments by `type` column. Which categories (architecture, parameter, simplification, algorithmic, infrastructure) have the highest keep rate? Which have the highest crash rate?

### 2. Select a strategy

Use the first matching rule:

| Condition | Strategy | What it means |
|-----------|----------|---------------|
| Crash rate >40% | **Stabilize** | Too many failures. Simplify your changes, reduce complexity, fix foundations before trying anything ambitious. |
| Hit rate >60% AND velocity positive | **Exploit** | You're in a productive vein. Keep refining the current approach with small, targeted changes. |
| 3+ consecutive `keep` but velocity declining | **Ablate** | You're adding complexity for diminishing returns. Remove components one at a time to find what's actually needed. |
| Multiple past `keep` experiments that haven't been combined | **Combine** | You have individual wins sitting in history. Try merging two or more previously successful changes. |
| Per-type data shows one category with >70% hit rate while others are <30% | **Specialize** | You've found a productive experiment category. Focus the next batch exclusively on that type. |
| Hit rate >40% AND 2+ competing hypotheses in ideas backlog | **Branch** | You have competing hypotheses worth testing in parallel. Fork sub-branches, test each, merge the winner. See the branch protocol below. |
| Hit rate <20% AND velocity flat or negative | **Explore** | Current approach is exhausted. Try something structurally different — a new algorithm, a different file, a fundamentally different strategy. |
| None of the above | **Continue** | No strong signal. Pick the most promising idea from your backlog and proceed. |

### 3. Extract meta-patterns

Look across all of `results.tsv`, not just the last batch:

- **File-level patterns** — which files appear most often in successful experiments? Which in crashes?
- **Category patterns** — compute keep rate per `type` across all results. Which experiment types are most productive? If a category has >5 attempts and <10% success, deprioritize it. Shift effort toward high-hit-rate categories.
- **Plateau detection** — has the metric stopped improving? How many experiments since the last `keep`?
- **Anomaly review** — any result that's surprisingly good or bad? Could it be measurement noise?

### 4. Check measurement hygiene

If recent results show high variance (similar changes producing very different numbers), suspect runtime noise rather than real signal:

- Re-run the last `keep` experiment to confirm the improvement is real.
- Be aware of JIT warmup, garbage collection pauses, and background processes.
- If two measurements of the same code differ by more than 10%, note the variance in `autoresearch.md` and consider running multiple times before concluding.

### 5. Update your theory

Maintain a `## Current theory` section at the **top** of `autoresearch.md` (below the title). Update it at every checkpoint. This is your model of the system:

- What you believe affects the metric
- What you've tested and ruled out
- What you haven't tested yet
- Your prediction for the most promising next direction

### 6. Write the review

Add a section to `autoresearch.md`:

```
### Strategic review after experiment N
**Hit rate:** X/{{checkpoint_interval}} keeps (Y%)
**Velocity:** <improving / steady / declining>
**Diversity:** <high / medium / low>
**Crash rate:** Z%
**Strategy for next batch:** <exploit / explore / ablate / combine / stabilize / continue>
**Rationale:** <1-2 sentences on why>
```

Then resume the experiment loop with your chosen strategy guiding your next hypothesis."""

# ── Adaptive rigor escalation block ──────────────────────────────────

ADAPTIVE_ESCALATION_BLOCK = """\

### Rigor escalation check

This session started in **light** mode for maximum experiment throughput. At each checkpoint, evaluate whether to escalate to **standard** mode:

- Hit rate below 30% in the last batch → **escalate**. Low hit rates mean you need more disciplined hypothesis formation.
- Velocity flat or declining for 2+ consecutive checkpoints → **escalate**. Plateaus need deeper causal analysis.
- 3+ crashes in the last batch → **escalate**. Frequent crashes suggest insufficient pre-experiment reasoning.

**To escalate:** Write "RIGOR ESCALATED TO STANDARD" in `autoresearch.md`. From that point forward, follow the standard scientific method: write a hypothesis before each experiment, change one variable at a time, and complete the full after-experiment analysis (result, vs hypothesis, root cause, learnings). Once escalated, do not de-escalate."""


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
    elif extractor == "composite":
        components = metric.get("components", [])
        if not components:
            print("Error: composite extractor requires metric.components list", file=sys.stderr)
            sys.exit(1)
        # Validate components
        if not isinstance(components, list) or not all(isinstance(c, dict) for c in components):
            print("Error: metric.components must be a list of mappings. Install PyYAML (pip install pyyaml) for complex configs, or use the interactive setup.", file=sys.stderr)
            sys.exit(1)
        total_weight = 0
        for comp in components:
            for field in ("name", "weight", "direction", "baseline"):
                if field not in comp:
                    print(f"Error: composite component missing '{field}'. Each component needs: name, weight, direction, baseline", file=sys.stderr)
                    sys.exit(1)
            total_weight += float(comp["weight"])
            if comp["direction"] not in ("lower", "higher"):
                print(f"Error: component '{comp['name']}' direction must be 'lower' or 'higher'", file=sys.stderr)
                sys.exit(1)
        if abs(total_weight - 1.0) > 0.01:
            print(f"Error: composite component weights must sum to 1.0, got {total_weight}", file=sys.stderr)
            sys.exit(1)

        # Build a Python script that extracts multiple METRIC lines and computes composite
        comp_defs = []
        for comp in components:
            comp_defs.append(
                f'    {{"name": "{comp["name"]}", "weight": {comp["weight"]}, '
                f'"direction": "{comp["direction"]}", "baseline": {comp["baseline"]}}}'
            )
        comp_json = ",\n".join(comp_defs)

        return (
            '{eval_cmd}\n'
            'python3 -c "\n'
            'import sys, re\n'
            'output = open(\".autoresearch_output\").read() if True else \"\"\n'
            'metrics = {{}}\n'
            'for line in output.split(chr(10)):\n'
            '    if line.startswith(\"METRIC \"):\n'
            '        pair = line[7:]\n'
            '        k, v = pair.split(\"=\", 1)\n'
            '        try: metrics[k] = float(v)\n'
            '        except: pass\n'
            'components = [\n'
            f'{comp_json}\n'
            ']\n'
            'score = 0.0\n'
            'for c in components:\n'
            '    val = metrics.get(c[\"name\"])\n'
            '    if val is None:\n'
            '        print(f\"WARNING: component {{c[\\\"name\\\"]}} not found in output\", file=sys.stderr)\n'
            '        continue\n'
            '    baseline = c[\"baseline\"]\n'
            '    if baseline == 0: baseline = 1\n'
            '    if c[\"direction\"] == \"lower\":\n'
            '        normalized = max(0, (2 * baseline - val) / baseline)\n'
            '    else:\n'
            '        normalized = val / baseline\n'
            '    score += c[\"weight\"] * normalized\n'
            '    print(f\"METRIC {{c[\\\"name\\\"]}}={{val}}\")\n'
            f'print(f\"METRIC {name}={{score:.4f}}\")\n'
            '"\n'
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
                # Check if this is a list-of-dicts (e.g. "- name: foo")
                item_match = re.match(r"^(\w+):\s*(.*)", value)
                if item_match:
                    # Start a dict item — first key:value is inline
                    item = {item_match.group(1): _cast(item_match.group(2).strip())}
                    item_indent = indent
                    # Collect subsequent indented key:value pairs
                    i += 1
                    while i < len(lines):
                        nline = lines[i]
                        nstripped = nline.strip()
                        if not nstripped or nstripped.startswith("#"):
                            i += 1
                            continue
                        nindent = len(nline) - len(nline.lstrip())
                        if nindent <= item_indent:
                            break  # Back to same or lower indent — done with this item
                        sub_match = re.match(r"^(\w+):\s*(.*)", nstripped)
                        if sub_match:
                            item[sub_match.group(1)] = _cast(sub_match.group(2).strip())
                        i += 1
                    result[current_key].append(item)
                    continue
                else:
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


def _parse_components_from_text(text):
    """Extract metric.components list-of-dicts directly from YAML text.

    Fallback for the simple parser which can't handle deeply nested structures.
    Looks for the 'components:' key under 'metric:' and parses the list items.
    """
    lines = text.split("\n")
    components = []
    in_components = False
    current_item = None
    comp_indent = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())

        if stripped == "components:":
            in_components = True
            comp_indent = indent
            continue

        if in_components:
            # End of components block — back to same or lower indent and not a list item
            if indent <= comp_indent and not stripped.startswith("-"):
                break

            if stripped.startswith("- "):
                # New component item
                if current_item:
                    components.append(current_item)
                current_item = {}
                # Parse inline key:value
                item_text = stripped[2:].strip()
                m = re.match(r"^(\w+):\s*(.*)", item_text)
                if m:
                    current_item[m.group(1)] = _cast(m.group(2).strip())
            elif current_item is not None:
                # Sub-key of current item
                m = re.match(r"^(\w+):\s*(.*)", stripped)
                if m:
                    current_item[m.group(1)] = _cast(m.group(2).strip())

    if current_item:
        components.append(current_item)

    return components if components else None


def parse_config(path):
    """Parse a lab.yaml file and return validated config dict."""
    text = Path(path).read_text()

    # Try stdlib yaml first (available in Python 3.x if PyYAML is installed)
    try:
        import yaml
        config = yaml.safe_load(text)
    except ImportError:
        config = parse_yaml_simple(text)
        # The simple parser can't handle list-of-dicts nested under a dict
        # (e.g. metric.components). Parse components manually if needed.
        metric = config.get("metric", {})
        if isinstance(metric, dict) and metric.get("extract", "").split(None, 1)[0:1] == ["composite"]:
            components = _parse_components_from_text(text)
            if components:
                metric["components"] = components
                # Clean up keys that leaked from components into metric
                for key in ("weight", "baseline"):
                    if key in metric and not isinstance(metric[key], list):
                        del metric[key]

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
    if rigor == "adaptive":
        config["scientist_block"] = SCIENTIST_LIGHT
    else:
        config["scientist_block"] = RIGOR_BLOCKS[rigor]

    # Validate and generate checkpoint_block
    checkpoint_interval = config.get("checkpoint_interval", 5)
    if checkpoint_interval is False or checkpoint_interval == 0:
        if rigor == "adaptive":
            # Adaptive rigor requires checkpoints — force default interval
            checkpoint_interval = 5
            print("Note: adaptive rigor requires checkpoints. Setting checkpoint_interval to 5.", file=sys.stderr)
        else:
            config["checkpoint_interval"] = 0
            config["checkpoint_block"] = ""
            config["has_checkpoint"] = False
    if checkpoint_interval:
        if not isinstance(checkpoint_interval, int) or checkpoint_interval < 1:
            print(f"Error: checkpoint_interval must be a positive integer or 0/false to disable, got '{checkpoint_interval}'", file=sys.stderr)
            sys.exit(1)
        config["checkpoint_interval"] = checkpoint_interval
        block = CHECKPOINT_BLOCK.replace("{{checkpoint_interval}}", str(checkpoint_interval))
        if rigor == "adaptive":
            block += ADAPTIVE_ESCALATION_BLOCK
        config["checkpoint_block"] = block
        config["has_checkpoint"] = True

    # Inject skills from previous sessions
    skills_path = Path.home() / ".autoresearch" / "skills.md"
    if skills_path.exists():
        content = skills_path.read_text().strip()
        if content:
            config["skills_block"] = content
            config["has_skills"] = True
        else:
            config["skills_block"] = ""
            config["has_skills"] = False
    else:
        config["skills_block"] = ""
        config["has_skills"] = False

    # Generate extraction_block
    extraction_block = _build_extraction_block(metric)
    if extraction_block:
        # Substitute {eval_cmd} with the actual eval command
        config["extraction_block"] = extraction_block.replace("{eval_cmd}", config["eval"].rstrip())
        config["has_extractor"] = True
    else:
        config["extraction_block"] = ""
        config["has_extractor"] = False

    # Inject calibration data if calibration.md exists
    cal_path = Path("calibration.md")
    if cal_path.exists():
        cal_text = cal_path.read_text()
        config["has_calibration"] = True
        # Parse key values from calibration report
        config["calibration_baseline"] = _extract_cal_field(cal_text, "Baseline")
        config["calibration_cv"] = _extract_cal_field(cal_text, "CV")
        config["calibration_verdict"] = _extract_cal_verdict(cal_text)
        config["calibration_runs"] = _extract_cal_runs(cal_text)
        cv_val = _extract_cal_cv_number(cal_text)
        if "noisy" in cal_text.lower() and cv_val:
            threshold = round(cv_val * 2, 1)
            config["calibration_warning"] = (
                f"Variance is high. Run experiments multiple times before concluding "
                f"an improvement is real. Treat improvements under {threshold}% with skepticism."
            )
        else:
            config["calibration_warning"] = ""
    else:
        config["has_calibration"] = False

    return config


def _extract_cal_field(text, field):
    """Extract a field value from calibration.md markdown."""
    for line in text.split("\n"):
        if f"**{field}:**" in line:
            # Strip markdown bold and leading dash
            val = line.split(f"**{field}:**", 1)[1].strip()
            return val
    return "unknown"


def _extract_cal_verdict(text):
    """Extract the stability verdict (stable/acceptable/noisy)."""
    for line in text.split("\n"):
        if "**CV:**" in line:
            for word in ("stable", "acceptable", "noisy"):
                if word in line:
                    return word
    return "unknown"


def _extract_cal_runs(text):
    """Extract the number of calibration runs."""
    import re as _re
    for line in text.split("\n"):
        if "**Baseline:**" in line:
            m = _re.search(r"median of (\d+)", line)
            if m:
                return m.group(1)
    return "3"


def _extract_cal_cv_number(text):
    """Extract the CV percentage as a float."""
    import re as _re
    for line in text.split("\n"):
        if "**CV:**" in line:
            m = _re.search(r"([\d.]+)%", line)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: parse_config.py <lab.yaml>", file=sys.stderr)
        sys.exit(1)
    config = parse_config(sys.argv[1])
    print(json.dumps(config, indent=2))
