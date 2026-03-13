# autoresearch-patterns

Scientific method in a box. Define what to optimize, point any AI agent at it, go to sleep. Wake up to results.

Based on [karpathy/autoresearch](https://github.com/karpathy/autoresearch) and [davebcn87/pi-autoresearch](https://github.com/davebcn87/pi-autoresearch).

## How it works

You tell autoresearch what to optimize. It generates a `program.md` — a self-contained instruction file that any AI agent can follow autonomously. The agent modifies code, measures the result, keeps improvements, discards regressions, and repeats until you stop it.

No daemon. No runner process. The agent IS the loop.

```
You write lab.yaml → autoresearch init → generates program.md → Agent follows it → Loop runs forever
```

## Install

```bash
curl -sL https://raw.githubusercontent.com/samzoloth/autoresearch-patterns/main/install.sh | bash
```

This clones the repo to `~/.autoresearch` and puts `autoresearch` on your PATH.

<details>
<summary>Manual install</summary>

```bash
git clone https://github.com/samzoloth/autoresearch-patterns ~/tools/autoresearch
ln -sf ~/tools/autoresearch/bin/autoresearch /usr/local/bin/autoresearch
```

</details>

**Requirements:** Python 3, Git, and whatever your eval command needs (pnpm, node, etc.). No pip install — stdlib only.

## Get started

### 1. Go to your project

```bash
cd my-project
```

Any git repo works. autoresearch creates its own branch, so your main branch stays clean.

### 2. Set up the lab

You have three options:

**Option A: Interactive setup** — autoresearch asks you 4 questions and generates everything.

```bash
autoresearch init
```

It will ask:
1. What are you optimizing? (name + description)
2. How do you measure it? (eval command, metric name, direction)
3. What files can the agent change?
4. Any constraints?

Then it generates `lab.yaml` and all session files in one step.

**Option B: Copy an example** — start from a pre-built config and customize.

```bash
autoresearch examples              # see what's available
autoresearch examples copy test-speed
vim lab.yaml                       # tweak for your project
autoresearch init
```

**Option C: Write lab.yaml by hand** — full control.

```bash
cat > lab.yaml << 'EOF'
name: optimize-test-speed
description: Reduce vitest test suite execution time

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
  - vitest.config.ts
  - src/

immutable:
  - src/**/*.test.ts
  - package.json

constraints:
  - All tests must pass (exit code 0)
  - No new dependencies
  - No removing or skipping tests
EOF

autoresearch init
```

### 3. Validate before committing (optional)

```bash
autoresearch init --dry-run
```

This parses your config, checks for common mistakes (like a missing METRIC output line), and shows what would be generated — without writing anything.

### 4. Start an agent

Any agent that can read markdown and run shell commands works:

```bash
# Claude Code
claude "Read program.md and follow the instructions exactly."

# Codex
codex "Read program.md and follow the instructions exactly."

# Cursor — open program.md, tell the agent to follow it
# Pi — same approach
```

The agent reads `program.md`, understands the full loop, and starts running experiments autonomously. The first run establishes a baseline, then it starts trying improvements.

### 5. Go do something else

The agent runs indefinitely. Each experiment takes however long your eval command takes. For a test suite that runs in 30 seconds, you'll get ~120 experiments per hour.

Check in anytime:

```bash
# See the experiment log
cat results.tsv

# See what the agent has learned
cat autoresearch.md

# See the commit history (each kept experiment = one commit)
git log --oneline
```

### 6. Resume after interruption

If the agent stops (context limit, crash, you killed it), start a new one:

```bash
claude "Read program.md and follow the instructions exactly."
```

The new agent reads `autoresearch.md`, `results.tsv`, and `git log` to understand what's been tried, then picks up where the last session left off. If there's an `autoresearch.ideas.md` with deferred ideas, it uses those as inspiration.

### 7. Merge results

When you're happy with the improvements:

```bash
git checkout main
git merge autoresearch/optimize-test-speed-20260313
```

The branch history is monotonically improving — every commit on it made the metric better (or simplified the code at equal performance). Failed experiments are reverted, so they never appear in the branch.

## What autoresearch init generates

All files are created in your project directory on a new git branch (`autoresearch/<name>-<date>`):

| File | Purpose |
|------|---------|
| `program.md` | Complete agent instructions — the agent reads this one file and knows everything |
| `benchmark.sh` | Eval harness wrapping your eval command with a timeout, outputs `METRIC name=value` |
| `autoresearch.md` | Living session document — objective, files in scope, what's been tried (agent updates this) |
| `results.tsv` | Tab-separated experiment log (agent appends each result) |
| `autoresearch.ideas.md` | Ideas backlog for promising but deferred experiments |

## The METRIC output format

Your eval command must output a line like this:

```
METRIC duration_seconds=4.2
```

The benchmark harness wraps your command with a timeout and passes through any line starting with `METRIC`. If your eval command doesn't naturally produce this, add an echo at the end:

```yaml
eval: |
  pnpm test --run 2>&1
  echo "METRIC duration_seconds=$SECONDS"
```

`autoresearch init` warns you if your eval command doesn't contain a METRIC line and shows you exactly what to add.

## Configuration reference

Minimal config — everything else has sensible defaults:

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

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | yes | — | Experiment name (used in branch name) |
| `description` | no | — | One-line description |
| `metric.name` | yes | — | Name of the metric to optimize |
| `metric.unit` | no | — | Unit label (seconds, KB, etc.) |
| `metric.direction` | yes | — | `lower` or `higher` |
| `eval` | yes | — | Shell command that outputs `METRIC name=value` |
| `mutable` | yes | — | Files/directories the agent may modify |
| `immutable` | no | `[]` | Files the agent must not touch |
| `constraints` | no | `[]` | Rules the agent must follow |
| `timeout` | no | `300` | Seconds before eval command is killed |

## Pre-built examples

```bash
autoresearch examples
```

| Config | Metric | Direction | Use case |
|--------|--------|-----------|----------|
| `test-speed` | duration_seconds | lower | Reduce test suite execution time |
| `bundle-size` | bundle_kb | lower | Minimize production JS bundle |
| `lighthouse` | perf_score | higher | Improve Lighthouse performance score |
| `build-speed` | build_seconds | lower | Speed up production build |
| `accessibility` | violations | lower | Fix axe-core a11y violations |
| `prompt-engineering` | eval_score | higher | Optimize LLM prompts against an eval |

## CLI reference

```
autoresearch init [--dry-run] [lab.yaml]    Set up a session (interactive if no lab.yaml)
autoresearch examples                       List available example configs
autoresearch examples copy <name>           Copy an example to ./lab.yaml
autoresearch help                           Show help
```

## How the loop works

The agent follows this cycle, autonomously, until interrupted:

1. **Pick an idea** — grounded in understanding the code, not random variation
2. **Modify files** — a single, focused change to files in scope
3. **Commit** — `git commit -m "experiment: <description>"`
4. **Run benchmark** — `./benchmark.sh > run.log 2>&1`
5. **Decide** — metric improved? keep the commit. Worse or equal? `git reset HEAD~1 --hard`
6. **Log** — append result to `results.tsv`, update `autoresearch.md`
7. **Repeat** — never ask "should I continue?", never stop

The simplicity criterion applies: removing code for equal performance is a win. Tiny improvements that add ugly complexity get discarded. The agent optimizes for the metric AND for code quality.

## Reference

The `reference/` directory contains the original source files from both implementations:

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — the original LLM training optimizer
- [davebcn87/pi-autoresearch](https://github.com/davebcn87/pi-autoresearch) — the domain-agnostic Pi adaptation
