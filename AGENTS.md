# AGENTS.md

## What this repo is

A configurable tool for running autonomous iterative experiments. Users write a `lab.yaml`, run `init.sh`, and get a generated `program.md` that any AI agent can follow to optimize a metric.

The key insight: `program.md` is the product. Everything else exists to generate a good one from user config.

## Architecture

```
lab.yaml → init.sh → (parse_config.py + render.py) → program.md + benchmark.sh + session files
```

## Structure

- `init.sh` — entry point, orchestrates config parsing and template rendering
- `lib/parse_config.py` — parses lab.yaml (stdlib only, tries PyYAML then falls back to simple parser)
- `lib/render.py` — renders templates with `{{var}}` substitution, `{{#each}}`, `{{#if}}`
- `templates/` — Handlebars-style templates for generated files
- `examples/` — pre-built lab.yaml configs for common optimization targets
- `reference/` — original source files from karpathy/autoresearch and pi-autoresearch

## Guidelines

- Python code uses stdlib only — no pip dependencies, ever
- Templates use `{{var}}` syntax with dot notation (`{{metric.name}}`)
- Generated `program.md` must be completely self-contained — no imports, no references to this repo
- The three invariants: immutable evaluation, mutable artifact, deterministic keep/discard
- `METRIC name=value` is the standard output format for benchmark scripts
- TSV for results (human-scannable, zero deps)
- Git reset HEAD~1 for reverts (keeps branch history monotonically improving)

## Testing changes

After modifying templates or lib code, verify by running `init.sh` with each example yaml in a test git repo and checking the generated files make sense.
