# Exploration 001: Agent-Agnostic Harness Design

How to make the autoresearch pattern work with any agent, not just one host.

## The abstract autoresearch machine

Minimal state machine, stripped of all implementation details:

```
Init -> BaselineEstablished -> Propose -> ApplyChange -> Execute -> Evaluate
  -> Accept (if better under policy)  -> Log -> Propose (loop)
  -> Reject (if not better)           -> Log -> Propose (loop)
  -> Fail   (crash/timeout/invalid)   -> Log -> Propose (loop)

Terminal: Pause | Stop | Reconfigure (new segment/baseline)
```

### Invariants (non-negotiable)
1. Single canonical best per segment
2. Every attempt is logged (including crash/timeout)
3. Evaluator is stable within a segment (same metric + direction)
4. Reject/fail path never mutates canonical best
5. Decision policy is deterministic given run data

### Essential vs implementation choice

**Essential:** iterative propose→run→evaluate→decide loop, durable experiment ledger, explicit accept/reject/fail outcomes, budget constraints, resume capability after interruption.

**Implementation choice:** git vs snapshots, JSONL vs TSV vs SQLite, LLM proposals vs scripted search, CLI parsing vs structured results, agent host.

---

## Coupling inventory

Seven layers where both implementations have coupling:

### Agent layer
- Host-specific APIs/events (Pi extension lifecycle, Claude conversational startup)
- Prompt-shaping mechanisms vary by host
- Context-window assumptions (avoid flooding, rely on chat memory)
- **Portable core:** tool semantics (init/run/log) and loop discipline

### Runtime layer
- Unix/POSIX shell assumptions (bash, grep, tail, redirection)
- Python uv (original), Node/TS (Pi)
- Path conventions
- **Portable core:** "execute command with timeout + capture outputs + status"

### Domain layer
- Original is LLM-training flavored (val_bpb, tokens, mfu)
- Pi is mostly domain-neutral but coding-centric
- **Portable core:** scalar objective + optional diagnostics map

### State layer
- Git branch/commit as checkpointing (both implementations)
- JSONL append-only history with segment headers (Pi)
- TSV untracked ledger (original)
- **Portable core:** append-only attempt history + canonical best pointer + segment concept

### Evaluation layer
- Original: regex parsing from logs, crash inferred by missing line (brittle)
- Pi: explicit metric passed to log_experiment (stronger)
- **Portable core:** typed run result contract: {status, primary_metric, secondary_metrics}

### Session layer
- Long-lived unattended run assumptions
- Host event lifecycle drives reconstruction (Pi)
- Context reset risks duplicate attempts
- **Portable core:** full state reconstruction from files only; host memory is optional

### Communication layer
- Conversational control plane (original)
- Queued user steers during runs (Pi)
- **Portable core:** explicit control signals + status artifacts

---

## Core design thesis

**The harness should be a FILE PROTOCOL, not an API.**

Every agent can read and write files. Not every agent can call your custom API. Files are the universal agent interface.

---

## Concrete file protocol (v0.1)

```
.autoresearch/
  autoresearch.yaml       # session config (metric, direction, budget, runner)
  autoresearch.md         # agent-facing operating doc (objective, constraints, what's been tried)
  autoresearch.jsonl      # append-only experiment ledger (source of truth)
  state.json              # derived snapshot (recomputed from jsonl replay)
  control.json            # human/automation control signals (pause/stop/reconfigure)
  policy.yaml             # decision rules (keep thresholds, guardrails)
  ideas.md                # deferred experiment ideas backlog
  scripts/
    run.sh                # benchmark runner (outputs metrics.json)
    evaluate.sh           # optional metric extraction helper
  runs/
    exp-<id>/
      stdout.log
      stderr.log
      metrics.json        # {primary_metric, secondary_metrics, telemetry}
      diff.patch           # what changed
      metadata.json        # proposal description, timestamps
```

### autoresearch.yaml
```yaml
name: "margin-render-speed"
objective:
  primary_metric: "p95_render_ms"
  direction: "lower"
  unit: "ms"
budget:
  max_run_seconds: 600
  max_attempts: 200
  max_failures_in_row: 5
environment:
  cwd: "."
  runner: ".autoresearch/scripts/run.sh"
segment: 1
```

### autoresearch.jsonl events
Event types: config_initialized, proposal_created, run_executed, evaluation_recorded, decision_made, segment_started, control_applied

```json
{"ts":"2026-03-13T21:10:04Z","segment":1,"event":"decision_made","experiment_id":"exp-0012","status":"success","primary_metric":412.4,"decision":"keep","reason":"-18.2ms vs best"}
```

### state.json (derived, overwritten on each event)
```json
{
  "segment": 1,
  "best_experiment_id": "exp-0012",
  "best_primary_metric": 412.4,
  "attempts": 12,
  "failures_in_row": 0
}
```

### control.json (human/automation signals)
```json
{
  "command": "resume",
  "updated_at": "2026-03-13T21:12:00Z",
  "overrides": {"budget.max_run_seconds": 900}
}
```

### metrics.json (per-run output contract)
```json
{
  "primary_metric": 412.4,
  "secondary_metrics": {"bundle_kb": 317.2, "a11y_score": 99},
  "telemetry": {"duration_ms": 201234}
}
```

---

## Agent adapters (thin by design)

The protocol is files. Each agent just needs to know how to read/write them.

### Claude Code / Codex
- AGENTS.md points to .autoresearch/autoresearch.md
- Agent reads config, proposes changes, runs benchmark via terminal
- Appends JSONL events via shell helper or direct file write
- Checks control.json each loop iteration

### Pi
- Extension becomes convenience layer over file protocol
- init/run/log tools write to protocol files as source of truth
- Dashboard reads state.json + autoresearch.jsonl
- Session reconstruction from files first, Pi history fallback second

### Cursor
- .cursorrules instructs agent to obey file protocol
- Commands via terminal panel
- File state is canonical; Cursor memory is optional bonus

### Raw CLI (bash)
- Shell script loop: read state.json -> propose -> run benchmark -> evaluate -> decide -> append jsonl
- No agent needed for scripted search; agent optional for creative proposals

---

## Multi-objective extensions

### Primary + guardrails (v1, ship this first)
- Optimize primary metric
- Reject changes that violate guardrails beyond threshold
- Guardrails defined in policy.yaml

### Sequential segments (v2)
- Segment 1: optimize performance
- Segment 2: optimize accessibility (perf becomes guardrail)
- Segment 3: optimize bundle size (perf + a11y become guardrails)
- Each segment inherits prior winner as baseline

### Parallel lanes (v3)
- Isolated workspaces per objective
- Periodic reconciliation evaluates lane winners against global policy

---

## Applying to projects

### Margin (best first target)
- **Primary metric:** annotation-open-to-interactive p95 (ms), lower is better
- **Secondary:** memory MB, error count, dropped frames
- **Artifact:** components and rendering code
- **Eval:** deterministic test corpus (3-5 fixture docs), Playwright-driven timing, average over N runs
- **Constraints:** no visual regression, highlights must survive, tests must pass
- **Why first:** local dev control, measurable metrics, rapid iteration, high portfolio/case-study value

### Portfolio site (good second target)
- **Primary metric:** Lighthouse perf score, higher is better
- **Secondary:** LCP p75 ms, CLS, JS bundle KB
- **Eval:** scripted Lighthouse against fixed URL set + throttling profile
- **Lower complexity, good for protocol validation**

### Recommendation
Ship the file protocol by building the Margin performance loop first. It exercises real complexity and produces case-study evidence.

---

## Implementation plan

1. Define protocol v0.1 (the file structure above)
2. Build run.sh + evaluate.sh for Margin
3. Write autoresearch.md for the Margin objective
4. Build Claude Code adapter (AGENTS.md + skill pointing at protocol)
5. Run first overnight loop
6. Iterate on protocol based on what breaks
7. Extract reusable harness scripts
8. Port to second project (portfolio site) to validate portability

Then commit it to the autoresearch-patterns/explorations/ folder and stage and commit with message "feat: add exploration 001 — agent-agnostic harness design"