# autoresearch-patterns

Exploring the autoresearch loop as a generalizable pattern for recursive self-improvement toward any goal.

## Origin

[karpathy/autoresearch](https://github.com/karpathy/autoresearch) — an autonomous AI agent that iteratively improves an LLM training script overnight. The agent modifies code, trains for 5 minutes, evaluates, keeps or discards, and repeats ~100 times while you sleep.

[davebcn87/pi-autoresearch](https://github.com/davebcn87/pi-autoresearch) — a Pi agent adaptation that abstracts the pattern into domain-agnostic infrastructure: any command, any metric, any optimization target. Shows the path from LLM-specific to universal.

## The core abstraction

Three invariants that generalize beyond LLM training:

1. **Immutable evaluation** — a fixed, trusted metric the agent can't game
2. **Mutable artifact** — a single surface the agent modifies (code, config, prose, design)
3. **Deterministic keep/discard** — improvement advances state; regression rolls back

The human's job shifts from doing the work to **programming the program** — writing the instructions that define the agent's search space, constraints, and judgment criteria.

## Two implementations, one pattern

| | Karpathy (original) | Pi adaptation |
|---|---|---|
| **Agent** | Claude/Codex (any) | Pi specifically |
| **Domain** | LLM pretraining | Any (test speed, bundle size, Lighthouse, etc.) |
| **Artifact** | train.py | Any file(s) in scope |
| **Metric** | val_bpb | Any numeric metric |
| **State** | Git branches + results.tsv | Git branches + autoresearch.jsonl |
| **Instructions** | program.md (static) | SKILL.md + autoresearch.md (living document) |
| **Loop control** | Agent reads program.md once | Extension injects rules into every turn |
| **Persistence** | TSV (append) | JSONL (append + config headers) |
| **Session resume** | Read results.tsv + git log | Read autoresearch.md + jsonl (survives context resets) |
| **User interaction** | None (async overnight) | Queued steers delivered after log_experiment |
| **Observability** | grep run.log | Live widget + dashboard (Ctrl+X) |
| **Ideas backlog** | None | autoresearch.ideas.md for deferred experiments |

### What pi-autoresearch adds

The key architectural insight: separate **infrastructure** (extension: run/log/display) from **domain knowledge** (skill: what to optimize, how). This means one extension serves unlimited domains.

It also solves practical problems the original doesn't address:
- **Context resets** — autoresearch.md is a living document that lets a fresh agent resume with full context
- **User steering** — messages queued during runs, delivered after log, no interruption
- **Ideas backlog** — promising but complex ideas written to autoresearch.ideas.md so they aren't lost
- **Benchmark script** — autoresearch.sh with pre-checks and METRIC output format standardizes evaluation

## Applying to domains

| Domain | Artifact | Metric | Eval time | Feasibility |
|--------|----------|--------|-----------|-------------|
| LLM pretraining | train.py | val_bpb ↓ | 5 min | Proven |
| Test speed | test configs, code | seconds ↓ | seconds-minutes | High |
| Bundle size | components, imports | KB ↓ | seconds | High |
| Lighthouse/CWV | components, styles | perf score ↑ | 30-60s | High |
| Build speed | configs, code | seconds ↓ | seconds-minutes | High |
| Accessibility | components | axe violations ↓ | seconds | High |
| Type coverage | source files | % covered ↑ | seconds | Medium |
| Prompt engineering | prompt text | eval score ↑ | variable | Medium |
| Writing quality | prose | readability score ↑ | seconds | Experimental |
| Design iteration | CSS/components | composite score | needs human eval | Hard |

## Open questions

- How do you define "val_bpb" for subjective domains (writing quality, design taste)?
- Can you chain multiple loops (one for perf, one for a11y, one for bundle size)?
- What's the minimum eval cycle time that makes overnight runs worthwhile?
- How do you handle multi-objective optimization where metrics trade off?
- What happens when the agent exhausts easy wins — change program.md or the search space?
- How do you prevent the agent from gaming the metric (Goodhart's law)?
- What's the right granularity for the mutable artifact — one file? multiple files? a directory?

## Structure

- reference/ — original source files from both repos for study
- explorations/ — domain-specific experiments and write-ups  
- programs/ — program.md variants for different domains

## References

- [Original autoresearch repo](https://github.com/karpathy/autoresearch)
- [Pi autoresearch adaptation](https://github.com/davebcn87/pi-autoresearch)
- [Karpathy tweet thread](https://x.com/karpathy/status/2029701092347630069)
