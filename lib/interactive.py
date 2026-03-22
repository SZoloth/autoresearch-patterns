#!/usr/bin/env python3
"""Interactive lab.yaml generator. Stdlib only."""

import sys


def prompt(question, hint="", required=True):
    """Prompt user for a single-line input."""
    if hint:
        print(f"  {hint}")
    result = input(f"{question}: ").strip()
    if required and not result:
        print("  This field is required.")
        return prompt(question, hint, required)
    return result


def prompt_multi(question, hint=""):
    """Prompt user for multiple lines. Empty line to finish."""
    if hint:
        print(f"  {hint}")
    print("  (one per line, empty line to finish)")
    lines = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        lines.append(line)
    return lines


def prompt_choice(question, choices):
    """Prompt user to pick from a list of choices."""
    result = ""
    while result not in choices:
        result = input(f"{question} ({'/'.join(choices)}): ").strip().lower()
    return result


def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else "lab.yaml"

    print()
    print("autoresearch — interactive setup")
    print("=" * 40)

    # Q1: What are you optimizing?
    print()
    print("1. What are you optimizing?")
    name = prompt("   Name",
                  hint="Slug for branch name, e.g. reduce-bundle-size")
    name = name.lower().replace(" ", "-")
    name = "".join(c for c in name if c.isalnum() or c == "-")

    description = prompt("   Description (one sentence)", required=False)

    # Q2: How do you measure it?
    print()
    print("2. How do you measure it?")
    print()
    metric_name = prompt("   Metric name",
                         hint="e.g. duration_seconds, bundle_kb, perf_score")
    metric_unit = prompt("   Unit (e.g. seconds, KB, points)", required=False)
    metric_dir = prompt_choice("   Lower or higher is better?", ["lower", "higher"])

    print()
    print("   How should the metric be extracted?")
    print("     1) duration    — auto-time the eval command (seconds)")
    print("     2) file-size   — measure a file/directory size (KB)")
    print("     3) regexp      — capture a number from output")
    print("     4) manual      — I'll output METRIC %s=<value> myself" % metric_name)
    print("     5) composite   — weighted combination of multiple metrics")
    print()
    extractor_choice = ""
    while extractor_choice not in ("1", "2", "3", "4", "5"):
        extractor_choice = input("   Choice [1-5]: ").strip()

    extract_value = ""
    components = []
    if extractor_choice == "1":
        extract_value = "duration"
    elif extractor_choice == "2":
        extract_path = prompt("   Path to measure", hint="e.g. dist/, build/output.js")
        extract_value = f"file-size {extract_path}"
    elif extractor_choice == "3":
        extract_pattern = prompt("   Regex pattern",
                                 hint="Must have a capture group, e.g. (\\d+) violations")
        extract_value = f"regexp {extract_pattern}"
    elif extractor_choice == "5":
        extract_value = "composite"
        print()
        print("   Define component metrics (your eval must output METRIC <name>=<value> for each).")
        print("   Weights must sum to 1.0.")
        print()
        while True:
            comp_name = prompt("   Component metric name (empty to finish)", required=False)
            if not comp_name:
                if not components:
                    print("  At least one component is required.")
                    continue
                break
            comp_weight = prompt(f"   Weight for {comp_name} (0.0-1.0)")
            comp_dir = prompt_choice(f"   Direction for {comp_name}?", ["lower", "higher"])
            comp_baseline = prompt(f"   Baseline value for {comp_name}")
            components.append({
                "name": comp_name,
                "weight": float(comp_weight),
                "direction": comp_dir,
                "baseline": float(comp_baseline),
            })

    print()
    if extract_value:
        eval_cmd = prompt("   Eval command",
                          hint="Shell command to run (metric extraction is automatic)")
    else:
        print("   Your eval command must output: METRIC %s=<number>" % metric_name)
        print("   Example:")
        print('     pnpm test 2>&1 && echo "METRIC %s=$(some_value)"' % metric_name)
        print()
        eval_cmd = prompt("   Eval command",
                          hint="Shell command that runs + outputs the METRIC line")

    # Q3: Mutable files
    print()
    print("3. What files/directories can the agent modify?")
    mutable = prompt_multi("   Mutable paths",
                           hint="Paths relative to project root, e.g. src/, vite.config.ts")
    while not mutable:
        print("  At least one mutable path is required.")
        mutable = prompt_multi("   Mutable paths")

    # Q4: Constraints (optional)
    print()
    print("4. Any constraints? (optional)")
    constraints = prompt_multi("   Constraints",
                               hint="Rules the agent must follow, e.g. 'All tests must pass'")

    # Q5: Rigor level
    print()
    print("5. How much scientific rigor?")
    print("     1) light    — log results, maintain ideas backlog")
    print("     2) standard — hypothesize, one-variable, structured analysis (recommended)")
    print("     3) strict   — repeat runs for confidence, control experiments")
    print("     4) adaptive — start light, escalate to standard when improvements plateau")
    print()
    rigor_choice = ""
    while rigor_choice not in ("1", "2", "3", "4"):
        rigor_choice = input("   Choice [1-4, default 2]: ").strip() or "2"
    rigor = {"1": "light", "2": "standard", "3": "strict", "4": "adaptive"}[rigor_choice]

    # Build YAML
    lines = [f"name: {name}"]
    if description:
        lines.append(f"description: {description}")
    lines.append("")
    lines.append("metric:")
    lines.append(f"  name: {metric_name}")
    if metric_unit:
        lines.append(f"  unit: {metric_unit}")
    lines.append(f"  direction: {metric_dir}")
    if extract_value:
        lines.append(f"  extract: {extract_value}")
    if components:
        lines.append("  components:")
        for comp in components:
            lines.append(f"    - name: {comp['name']}")
            lines.append(f"      weight: {comp['weight']}")
            lines.append(f"      direction: {comp['direction']}")
            lines.append(f"      baseline: {comp['baseline']}")
    lines.append("")
    lines.append("eval: |")
    for eval_line in eval_cmd.split("\n"):
        lines.append(f"  {eval_line}")
    lines.append("")
    lines.append("mutable:")
    for m in mutable:
        lines.append(f"  - {m}")
    if constraints:
        lines.append("")
        lines.append("constraints:")
        for c in constraints:
            lines.append(f"  - {c}")
    lines.append("")
    if rigor != "standard":
        lines.append(f"rigor: {rigor}")
        lines.append("")

    yaml_content = "\n".join(lines)

    # Preview
    print()
    print("-" * 40)
    print(yaml_content)
    print("-" * 40)

    confirm = input(f"Write to {output_path}? [Y/n] ").strip()
    if confirm.lower() in ("n", "no"):
        print("Aborted.")
        sys.exit(1)

    with open(output_path, "w") as f:
        f.write(yaml_content)

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
