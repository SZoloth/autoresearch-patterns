---
name: pstack-project
description: Apply pstack to autoresearch-patterns, using the existing project controls and evidence boundaries.
---

# Autoresearch patterns

Use `/Users/samzoloth/.codex/skills/pstack-workflow/SKILL.md`. Read AGENTS.md; `program.md` generation is the product. Trace `init.sh`, `lib/parse_config.py` and `lib/render.py`.

## Verification route

Use a newly created disposable Git fixture for the existing example configs. Inspect init.sh before running: it creates branches and state. Check generated program.md and benchmark.sh, then the documented record/fork/tree/status flow only inside that fixture.

Preserve immutable evaluation, mutable artifact, deterministic keep/discard, append-only results and failed experiment evidence. A valid generated file is not proof the experiment improved the real metric.

Do not initialize the user's active checkout, start autonomous loops, install global links or run paid benchmarks during setup. Keep Python stdlib-only.

This is a source-grounded engineering route, not a certified end-to-end verifier. Record fresh results and remaining gaps for the feature actually changed.
