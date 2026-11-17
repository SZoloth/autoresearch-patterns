# autoresearch-patterns: what the harness posts mean for this repo

Repo: SZoloth/autoresearch-patterns (public). Written 2026-11-16 from the default branch as it stood that day. Nothing was changed on GitHub.

## Source

- Post: [Shishira (@ShishiraReddy05), Nov 16, 2026](https://x.com/ShishiraReddy05/status/2122327324632686967). She had asked the night before for beginner material on harness engineering, then posted three X articles as "must read". No thread; her only other reply says she wants "content which help build own harness".
- [Theo, "What is a 'harness'?"](https://x.com/theo/status/2113424203345265053) (Oct 23, 2026)
- [Harrison Chase, "Your harness, your memory"](https://x.com/hwchase17/status/2042978500567609738) (Apr 11, 2026), which leans on [Sarah Wooders, "Why memory isn't a plugin (it's the harness)"](https://x.com/sarahwooders/status/2040121230473457921) and LangChain's ["The Anatomy of an Agent Harness"](https://blog.langchain.com/the-anatomy-of-an-agent-harness/)
- [Mohit Goyal, "I Built an Agentic Harness From Scratch"](https://x.com/ByteMohit/status/2063493300884246598) (Jun 7, 2026), with code at [MohitGoyal09/AgentForge](https://github.com/MohitGoyal09/AgentForge)

## What the sources say

**Theo: the harness is the plumbing, not the app.** A model only emits text. The harness is five things: tools that do work, a text syntax for calling them, a parser that spots calls and runs code, a way to return results to the model, and a list of tools with descriptions. Claude Code and Codex are an interface wrapped around a harness (Agent SDK, Codex App Server). Tools run inside the harness; MCP servers run "somewhere else" and are reached over a protocol. His kitchen analogy: model is the chef, harness is the kitchen, an app like T3 Code is a restaurant that lets you bring any kitchen. T3 Code exposes its cross-harness features (Claude threads spawning Codex subagents) as one MCP server instead of writing a plugin for every harness. "An agent is a harness plus an LLM," and most "different agents" are the same harness with different tools, instructions and MCP servers.

**Chase and Wooders: whoever owns the harness owns the memory.** Memory is context, and context management is the harness's core job. Wooders lists the hidden decisions a harness makes: how AGENTS.md or CLAUDE.md is loaded, how skill metadata is shown, whether the agent can edit its own instructions, what survives compaction, whether past interactions are stored and searchable, how much of the filesystem and working directory is exposed. Chase's ladder of lock-in: stateful APIs (server-side compaction, Responses API threads) are mildly bad; closed harnesses with unknown memory artifacts are bad; a whole harness plus long-term memory behind an API (Claude Managed Agents) is worst. Codex is open source but its compaction summary is encrypted and unusable elsewhere. His own email agent got deleted and the rebuilt one was far worse because the learned preferences were gone. The prescription: keep memory in open formats you control (AGENTS.md, skills, your own store) so you can switch models and harnesses. The LangChain post adds the standard component list: filesystem and git for durable state, bash as a general tool, sandboxes, memory files, compaction, offloading big tool outputs to files (keep head and tail), skills as progressive disclosure, Ralph loops (a hook that catches the model's attempt to stop and re-injects the goal), and planning plus self-verification.

**Goyal: the model is about 20% of the engineering.** "An agent is a runtime that controls how a model sees, acts, retries, remembers, and stops." The concrete techniques from AgentForge:

- *Session first.* Build the model's world (tools, MCP tools, visible skills, mode) before the first call.
- *The loop is a control system.* Turn budgets (smaller in plan mode), ordered model fallbacks with a circuit breaker that stops calling a failing provider, context-pressure checks with compaction, and a `LoopDetector` that flags three identical tool calls in a row or a repeating cycle of 2 to 5 actions and forces a final answer.
- *Tool results are observations, not logs.* Every tool returns a `ToolResult` with `summary`, `artifacts`, `next_actions` and `recovery_hint`; failures go through an `error_result` factory that fills in a default hint ("inspect the current state ... retry only if the action is still safe").
- *One registry pipeline.* Every result, local or MCP, passes cleanup, secret redaction, untrusted-content wrapping and hooks before the model sees it.
- *File tools expose hidden state.* Line numbers, offset/limit, binary detection, a truncation flag, trailing-newline status. Edits require a unique exact match and, on a miss, show similar lines and say "re-read, your copy may be stale". Patches reject absolute paths and `..`, and dry-run with `git apply --check`.
- *Approval is policy, not a vibe.* Modes (on-request, auto, auto-edit, never, yolo) classify commands, paths and danger flags in plain code. Plan mode removes write tools from the schema list, so the model can't call them at all.
- *Tool output is evidence, not authority.* File reads, shell output, web pages and MCP responses get wrapped as `<untrusted_content source=...>` with a note to treat it as data. (Its wrapper does not escape a forged closing tag inside the content, so it is a label, not a sandbox, which the author admits.)
- *Context is not a transcript.* Track token estimates, prune old tool output, compact older turns into a continuation summary that lists completed work, and count compaction's own token cost.
- *Skills are context budgeting.* `discover()` builds a metadata index; `load_skill()` spends context only when a skill is chosen.
- *MCP tools get namespaced* (`github__create_issue`) and go through the same registry, approvals and wrapping as built-in tools.
- *Subagents are tools first.* One goal in, one result out, scoped tools, max turns, hard timeout, read-only by default. Swarms are a later, separate problem.
- *Persistence is systems work.* Atomic writes, owner-only permissions, append-only JSONL event logs, and tests that run against an isolated home directory because his session tests were silently reading his real `~/Library/Application Support` state.
- *Test the boundaries, not the prose.* 278 tests, none needing a model call: blocked commands, secret stripping, unique-match edits, plan-mode filtering, snapshot round-trips, wrapper coverage.

His starter checklist: one model adapter, a loop with stop conditions, three typed tools, structured results with recovery hints, approval before writes, line-numbered reads, context pruning, one checkpoint, one skill, one namespaced MCP server, and one test where a tool fails and the model still gets a useful observation.

## What this repo is

Public. A stdlib-Python CLI (`bin/autoresearch`, `lib/*.py`) that generates a `program.md` from `templates/program.md.tmpl` so any coding agent can run a measure-keep-discard optimization loop overnight. "No daemon. No runner process. The agent IS the loop." State is git commits plus a ledger and a regenerated scratchpad (`lib/record.py`, `lib/scratchpad.py`, `lib/recover.py`, `lib/graph.py`, `lib/fork_node.py`). `explorations/001-harness-agnostic-design.md` argues the harness should be a file protocol, not an API, with invariants such as "every attempt is logged" and "reject/fail never mutates canonical best", and budgets like `max_failures_in_row`.

## What already matches the sources

- **Harness-neutral by design.** The file protocol is exactly Chase's "own your memory" stance: the ledger and scratchpad work in Codex, Claude Code, Pi or anything that reads files.
- **Durable, append-only history** and state rebuilt from files, the same persistence shape AgentForge uses.
- **Typed run result.** The exploration doc already calls for `{status, primary_metric, secondary_metrics}` instead of grepping logs.

## Suggested changes

The repo's weak spot is the one Goyal warns about: the stop conditions are prose. "The agent IS the loop" means the loop's safety rules live in `program.md.tmpl` text the model can ignore.

1. **Move "don't thrash" into `autoresearch record`.** The template says "If you've discarded the same idea twice, try something structurally different" and "Don't invest more than 2-3 attempts fixing a single crash." Make `lib/record.py` enforce it: hash the diff (or the `--description` plus touched files) for each discard and crash, and when the same signature appears a third time, or crashes in a row hit `budget.max_failures_in_row`, refuse the record and print a structured result: `status: blocked`, a `recovery_hint` naming the repeated idea, and `next_actions` such as "fork from the frontier node X" or "stop and write a summary". The agent reads CLI output, so this is a real boundary.
2. **Make the CLI output observations, not log lines.** Every `autoresearch` subcommand the agent calls (`record keep|discard|crash`, `fork`, `status`) should end with a short machine-readable block: what changed, the current best, the next safe move. AgentForge's `ToolResult` (`summary`, `artifacts`, `next_actions`, `recovery_hint`) is the model to copy.
3. **Enforce "NEVER run `git reset`" outside the prompt.** The template shouts it, which means it has happened. Two options: ship a Codex/Claude PreToolUse hook snippet in the README that blocks `git reset` and `git checkout -- .` in the lab directory, and have `lib/recover.py` checking at the start of every `record` call that HEAD still descends from the ledger's last kept commit, refusing to continue if not.
4. **Kill the regex metric path.** The template's crash detection is "If grep returns nothing, the run crashed." Have `templates/benchmark.sh.tmpl` write `metrics.json` with an explicit status, and have `record` read that file. A failed run then returns a typed observation instead of an empty grep.
5. **Add contract tests that need no agent.** The repo has no `tests/` directory. Goyal's point applies directly: test that `record` rejects a repeat, that `recover` rebuilds the same state from the ledger, that a discard never moves the best pointer. All deterministic, all cheap.

## What doesn't apply

- Approval modes and untrusted-content wrapping. The agent edits your own code against your own benchmark; there is little outside text in the loop. Exception: `examples/prompt-engineering.yaml`-style labs feed model outputs back in, which is worth labeling as data.
- Subagents and MCP namespacing. Out of scope for a single-agent loop.
