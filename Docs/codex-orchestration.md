# Codex Orchestration Context — Detective Agent

## Current repository layout

This workspace is a multi-repo project under one directory, not a single git root.

- `BE/`: FastAPI Backend. Single source of truth for sessions, rule engine, safe public payloads, AI gateway, Event Processor/SSE.
- `FE/`: React/Vite Frontend. Single-screen investigation desk, natural-language dialogue, BE API + SSE consumer.
- `AI/`: FastAPI/LangGraph-like internal AI service. CharacterAgent -> LightRuleCheck -> GameMasterAgent proposed events.

Each subdirectory has its own `.git` repository. Run git commands inside the relevant repo.

## Product direction to preserve

The MVP is a natural-language detective simulation. Do not turn it into a choice-button quiz. The stable design is:

`CharacterAgent -> LightRuleCheck -> GameMasterAgent(proposedEvents) -> BE Event Processor(validates/applies) -> SSE -> FE state updates`.

BE remains authoritative for rule verdicts and state mutation. AI never overwrites rules. FE reflects BE state.

## FE visual target

FE must match `FE/target/chatgpt-shared-detective-interface.png` as closely as practical. When orchestrating FE Codex work, make this image the primary UI reference and ask the FE agent to compare the rendered first/default screen against it before reporting completion. The target is a dark noir investigation dashboard with top nav, left suspect cards, central interrogation scene/input, right evidence grid + contradiction panel, and bottom internal-processing flow strip.

## Documentation added for Codex agents

- `BE/AGENTS.md`, `BE/SKILL.md`, `BE/Docs/commit-convention.md`
- `FE/AGENTS.md`, `FE/SKILL.md`, `FE/Docs/commit-convention.md`
- `AI/AGENTS.md`, `AI/SKILL.md`, `AI/Docs/commit-convention.md`

## Orchestration protocol

1. Capture tmux panes before sending new tasks.
2. Assign work to the owning repo agent first. Do not directly edit specialist code unless central integration/verification requires it.
3. Ask agents to report: changed files, validation commands, failures, and cross-repo contract changes.
4. Verify centrally after agents finish:
   - BE: `pytest -q`
   - FE: `npm run build`
   - AI: `pytest -q`
5. If a contract changes, update the matching `Docs/implementation.md` and tell counterpart agents the exact schema/endpoint delta.

## Code smell and observability standard

All repos should minimize:

- large god files/functions
- duplicated payload mapping
- hidden client/server truth divergence
- untyped request/response blobs
- silent broad exception swallowing
- logs containing secrets/private case truth/player free text by default

All repos should add structured logs with request/session/case IDs, duration, decision/event metadata, and fallback/error reason.
