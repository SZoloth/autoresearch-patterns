# AGENTS.md

## Project context

This is an exploration repo for generalizing the autoresearch pattern — recursive self-improvement loops driven by AI agents — beyond LLM training to arbitrary domains.

Two reference implementations studied:
- karpathy/autoresearch — the original LLM-specific version
- davebcn87/pi-autoresearch — the domain-agnostic Pi adaptation

## Structure

- reference/ — original source files from both repos
- explorations/ — domain-specific experiments and write-ups
- programs/ — program.md variants for different domains

## Guidelines

- This is a thinking/exploration repo, not a production codebase
- Preserve explorations even if they don't pan out — the learning matters
- When creating program.md variants, always include: objective function, mutable artifact, constraints, keep/discard criteria, session resume strategy
- The core pattern has three invariants: immutable evaluation, mutable artifact, deterministic keep/discard
- Think about what pi-autoresearch adds that the original lacks: living documents, user steering, ideas backlog, infrastructure/domain separation
