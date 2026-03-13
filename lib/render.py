#!/usr/bin/env python3
"""Template renderer. Replaces {{var}} and {{var.subvar}} with config values.

Supports simple conditionals:
  {{#if var}}...content...{{/if}}
  {{#each var}}...{{.}}...{{/each}}

Stdlib only — no pip dependencies.
"""

import re
import sys
import json
from pathlib import Path


def render(template, config):
    """Render a template string with config values."""
    result = template

    # Process {{#each key}}...{{.}}...{{/each}} blocks
    result = _process_each(result, config)

    # Process {{#if key}}...{{/if}} blocks
    result = _process_if(result, config)

    # Replace {{var.subvar}} dot-notation
    def replace_dotvar(match):
        path = match.group(1).strip()
        return str(_resolve(config, path))

    result = re.sub(r"\{\{(\w+\.\w+)\}\}", replace_dotvar, result)

    # Replace {{var}} simple variables
    def replace_var(match):
        key = match.group(1).strip()
        val = config.get(key, "")
        if isinstance(val, list):
            return "\n".join(f"- {item}" for item in val)
        if isinstance(val, dict):
            return str(val)
        return str(val)

    result = re.sub(r"\{\{(\w+)\}\}", replace_var, result)

    # Collapse triple+ newlines into double
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result


def _resolve(config, path):
    """Resolve a dot-notation path like 'metric.name' in config."""
    parts = path.split(".")
    current = config
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    return current


def _process_each(template, config):
    """Process {{#each key}}...{{.}}...{{/each}} blocks."""
    pattern = r"\{\{#each\s+(\w+)\}\}(.*?)\{\{/each\}\}"

    def replace(match):
        key = match.group(1)
        body = match.group(2).strip()
        items = config.get(key, [])
        if not isinstance(items, list):
            return ""
        return "\n".join(body.replace("{{.}}", str(item)) for item in items)

    return re.sub(pattern, replace, template, flags=re.DOTALL)


def _process_if(template, config):
    """Process {{#if key}}...{{/if}} blocks."""
    pattern = r"\{\{#if\s+(\w+)\}\}(.*?)\{\{/if\}\}"

    def replace(match):
        key = match.group(1)
        body = match.group(2)
        val = config.get(key, None)
        if val and (not isinstance(val, list) or len(val) > 0):
            return body.strip("\n")
        return ""

    return re.sub(pattern, replace, template, flags=re.DOTALL)


def render_file(template_path, config, output_path=None):
    """Render a template file with config values. Optionally write to output_path."""
    template = Path(template_path).read_text()
    rendered = render(template, config)
    if output_path:
        Path(output_path).write_text(rendered)
    return rendered


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: render.py <template> <config.json>", file=sys.stderr)
        print("  config.json is the output of parse_config.py", file=sys.stderr)
        sys.exit(1)
    config = json.loads(Path(sys.argv[2]).read_text())
    print(render_file(sys.argv[1], config))
