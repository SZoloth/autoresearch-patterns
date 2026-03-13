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
