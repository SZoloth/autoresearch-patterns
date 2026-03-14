# autoresearch-patterns

> If it can be measured, it can be improved.

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
curl -sL https://raw.githubusercontent.com/SZoloth/autoresearch-patterns/main/install.sh | bash
```

This clones the repo to `~/.autoresearch` and puts `autoresearch` on your PATH.

<details>
<summary>Manual install</summary>

```bash
git clone https://github.com/SZoloth/autoresearch-patterns ~/tools/autoresearch
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

**Option A: Interactive setup** — autoresearch asks you 5 questions and generates everything.

```bash
autoresearch init
```

It will ask:
1. What are you optimizing? (name + description)
2. How do you measure it? (metric name, direction, extractor)
3. What files can the agent change?
4. Any constraints?
5. How much scientific rigor? (light / standard / strict)

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
  extract: duration

eval: pnpm test --run 2>&1

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

rigor: standard
EOF

autoresearch init
```

### 3. Verify your setup

```bash
autoresearch test
```

This runs `benchmark.sh` once and shows the result with context:

```
Running benchmark...

  duration_seconds = 45 seconds  (baseline)

  Baseline recorded. Run autoresearch start to begin optimization.
```

On subsequent runs, it compares against the current best:

```
  duration_seconds = 29 seconds  new best! ↓36% from baseline
```

### 4. Start an agent

```bash
autoresearch start
```

This auto-detects available agents (Claude Code, Codex) and launches with the right prompt. You can also specify one:

```bash
autoresearch start --agent claude
autoresearch start --agent codex
```

Or start any agent manually:

```bash
claude "Read program.md and follow the instructions exactly."
cursor   # open program.md, tell the agent to follow it
```

### 5. Go do something else

The agent runs indefinitely. Each experiment takes however long your eval command takes. For a test suite that runs in 30 seconds, you'll get ~120 experiments per hour.

Check in anytime:

```bash
autoresearch status
```

```
  optimize-test-speed
  Reduce vitest test suite execution time
  ────────────────────────────────────────────
  Runs         5       ▁▅▃██
  Best         29 seconds
  Latest       29 seconds
  Improvement  +35.6%
  Streak       2 consecutive improvements

  Last 5 runs:
    45 seconds  baseline
    38 seconds ↓16%  parallelize tests
    42 seconds ↑11%  revert partial
    31 seconds ↓26%  shared fixtures
    29 seconds ↓6% *  final optimization
```

### 6. Resume after interruption

If the agent stops (context limit, crash, you killed it), start a new one:

```bash
autoresearch start
```

The new agent reads `autoresearch.md`, `results.tsv`, and `git log` to understand what's been tried, then picks up where the last session left off. If there's an `autoresearch.ideas.md` with deferred ideas, it uses those as inspiration.

### 7. Merge results

When you're happy with the improvements:

```bash
git checkout main
git merge autoresearch/optimize-test-speed-20260313
```

The branch history is monotonically improving — every commit on it made the metric better (or simplified the code at equal performance). Failed experiments are reverted, so they never appear in the branch.

## Metric extractors

Your eval command needs to output `METRIC name=value`. You can either handle this yourself or use a built-in extractor.

### Built-in extractors

Set `metric.extract` in lab.yaml and autoresearch handles the METRIC output for you:

| Extractor | What it does | Example |
|-----------|-------------|---------|
| `duration` | Times how long your eval command takes (seconds) | `extract: duration` |
| `file-size <path>` | Measures file/directory size in KB after eval runs | `extract: file-size dist/` |
| `regexp <pattern>` | Captures a number from eval output using a regex | `extract: regexp (\d+) violations` |

**Before** (manual timing with macOS-incompatible `date +%s%N`):
```yaml
eval: |
  START=$(date +%s%N)
  pnpm test --run 2>&1
  END=$(date +%s%N)
  echo "METRIC duration_seconds=$(( (END - START) / 1000000000 ))"
```

**After** (let the extractor handle it):
```yaml
eval: pnpm test --run 2>&1
metric:
  name: duration_seconds
  extract: duration
```

The `duration` extractor uses `python3` for portable timing that works on both macOS and Linux.

### Manual extraction

If you don't set `metric.extract`, your eval command must output the METRIC line itself. `autoresearch init` will warn you if it doesn't see one.

## Scientific rigor

The `rigor` field controls how much scientific discipline the agent applies. Default is `standard`.

```yaml
rigor: standard   # light | standard | strict
```

| Level | What the agent does |
|-------|-------------------|
| **light** | Log results, maintain ideas backlog |
| **standard** | Hypothesize before each experiment, change one variable at a time, analyze results against hypothesis, detect diminishing returns |
| **strict** | All of standard + run baseline 3x for variance, confirmation runs on improvements, control experiments every 5th run, full lab notebook entries |

**light** is for quick-and-dirty optimization where you just want the agent grinding.

**standard** is the sweet spot — the agent writes a hypothesis before each change, explains why results matched or didn't, and re-prioritizes ideas based on what it learned. This catches the common failure mode where agents make random changes without understanding why.

**strict** is for noisy metrics or when you need confidence in results. The agent establishes statistical baselines, confirms improvements with repeat runs, and periodically runs control experiments to catch drift.

## Configuration reference

Minimal config — everything else has sensible defaults:

```yaml
name: my-experiment
metric:
  name: duration_seconds
  direction: lower
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
| `metric.extract` | no | — | Built-in extractor: `duration`, `file-size <path>`, `regexp <pattern>` |
| `eval` | yes | — | Shell command to run (outputs `METRIC` if no extractor) |
| `mutable` | yes | — | Files/directories the agent may modify |
| `immutable` | no | `[]` | Files the agent must not touch |
| `constraints` | no | `[]` | Rules the agent must follow |
| `timeout` | no | `300` | Seconds before eval command is killed |
| `rigor` | no | `standard` | Scientific rigor level: `light`, `standard`, `strict` |

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
autoresearch test                           Run benchmark once and show result
autoresearch start [--agent <name>]         Launch an agent to optimize
autoresearch status                         Show session summary and results
autoresearch examples                       List available example configs
autoresearch examples copy <name>           Copy an example to ./lab.yaml
autoresearch help                           Show help
```

## How the loop works

The agent follows this cycle, autonomously, until interrupted:

1. **Hypothesize** — predict what will change and why, before touching code
2. **Modify files** — a single, focused change to files in scope
3. **Commit** — `git commit -m "experiment: <description>"`
4. **Run benchmark** — `./benchmark.sh > run.log 2>&1`
5. **Decide** — metric improved? keep the commit. Worse or equal? `git reset HEAD~1 --hard`
6. **Analyze** — compare result to hypothesis, update session notes
7. **Repeat** — never ask "should I continue?", never stop

The simplicity criterion applies: removing code for equal performance is a win. Tiny improvements that add ugly complexity get discarded. The agent optimizes for the metric AND for code quality.

## Reference

The `reference/` directory contains the original source files from both implementations:

- [karpathy/autoresearch](https://github.com/karpathy/autoresearch) — the original LLM training optimizer
- [davebcn87/pi-autoresearch](https://github.com/davebcn87/pi-autoresearch) — the domain-agnostic Pi adaptation
