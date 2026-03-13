# autoresearch-patterns

Scientific method in a box. Clone this repo, write a config, and let any AI agent run overnight experiments on your codebase.

Based on [karpathy/autoresearch](https://github.com/karpathy/autoresearch) and [davebcn87/pi-autoresearch](https://github.com/davebcn87/pi-autoresearch).

## How it works

```
lab.yaml → init.sh → program.md → Agent reads it → Loop runs forever
```

You define what to optimize. `init.sh` generates a self-contained `program.md` that any agent (Claude, Cursor, Codex, Pi) can follow autonomously. The agent modifies code, measures the result, keeps improvements, discards regressions, and repeats until you stop it.

No daemon. No runner process. The agent IS the loop.

## Quick start

```bash
# 1. Clone this repo somewhere
git clone https://github.com/samzoloth/autoresearch-patterns ~/tools/autoresearch

# 2. In your project, create a lab.yaml
cd my-project
cat > lab.yaml << 'EOF'
name: optimize-test-speed
metric:
  name: duration_seconds
  unit: seconds
  direction: lower
eval: |
  START=$(date +%s%N)
  pnpm test --run 2>&1
  END=$(date +%s%N)
  echo "METRIC duration_seconds=$(( (END - START) / 1000000000 ))"
mutable:
  - src/
EOF

# 3. Initialize
~/tools/autoresearch/init.sh

# 4. Start any agent
claude "Read program.md and follow the instructions exactly."

# 5. Go to sleep. Wake up to results.
cat results.tsv
```

## Configuration

`lab.yaml` is the only file you write. Minimal example:

```yaml
name: my-experiment
metric:
  name: duration_seconds
  unit: seconds
  direction: lower       # lower | higher
eval: pnpm test 2>&1
mutable:
  - src/
```

Full options:

```yaml
name: optimize-test-speed
description: Reduce vitest test suite execution time

metric:
  name: duration_seconds
  unit: seconds
  direction: lower

eval: pnpm test 2>&1     # command that produces METRIC output

mutable:                  # files the agent may change
  - vitest.config.ts
  - src/

immutable:                # files the agent must not touch
  - src/**/*.test.ts
  - package.json

constraints:              # rules the agent must follow
  - All tests must pass (exit code 0)
  - No new dependencies
  - No removing or skipping tests

timeout: 300              # seconds per experiment (default: 300)
```

## What init.sh generates

| File | Purpose |
|------|---------|
| `program.md` | Complete agent instructions — the agent reads this one file and knows everything |
| `benchmark.sh` | Eval harness wrapping your eval command, outputs `METRIC name=value` |
| `autoresearch.md` | Living session document — objective, files in scope, what's been tried |
| `results.tsv` | Experiment log (header row only at init) |
| `autoresearch.ideas.md` | Ideas backlog for deferred experiments |

It also creates a git branch `autoresearch/<name>-<date>` and commits all generated files.

## Eval command

Your eval command must output a line in this format:

```
METRIC metric_name=number
```

The benchmark harness wraps your command with a timeout and passes through METRIC lines. If your eval command doesn't output METRIC lines, add an echo at the end.

## Examples

Pre-built configs in `examples/`:

| Config | Metric | Direction | Use case |
|--------|--------|-----------|----------|
| `test-speed.yaml` | duration_seconds | lower | Reduce test suite time |
| `bundle-size.yaml` | bundle_kb | lower | Minimize JS bundle |
| `lighthouse.yaml` | perf_score | higher | Improve Lighthouse score |
| `build-speed.yaml` | build_seconds | lower | Speed up production build |
| `accessibility.yaml` | violations | lower | Fix a11y issues |
| `prompt-engineering.yaml` | eval_score | higher | Optimize LLM prompts |

Copy one and customize:

```bash
cp ~/tools/autoresearch/examples/test-speed.yaml lab.yaml
vim lab.yaml
~/tools/autoresearch/init.sh
```

## The loop

Once started, the agent follows this cycle indefinitely:

1. Pick an experiment idea
2. Modify files in scope
3. Commit the change
4. Run `./benchmark.sh`
5. If improved → keep the commit
6. If worse → `git reset HEAD~1 --hard`
7. Log to `results.tsv`, update `autoresearch.md`
8. Repeat forever

The agent never asks "should I continue?" — it runs until interrupted.

## Session resume

Stop the agent anytime. Start a new one later:

```bash
claude "Read program.md and follow the instructions exactly."
```

The new agent reads `autoresearch.md`, `results.tsv`, and `git log` to understand what's been tried, then continues from where the last session left off.

## Requirements

- Python 3 (stdlib only, no pip install needed)
- Git
- Whatever your eval command needs (pnpm, node, lighthouse, etc.)

## Reference

The `reference/` directory contains the original source files from both repos for study:

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — the original LLM training optimizer
- [davebcn87/pi-autoresearch](https://github.com/davebcn87/pi-autoresearch) — the domain-agnostic Pi adaptation
