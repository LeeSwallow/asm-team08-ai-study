---
name: detective-agent-ai
description: Use when implementing the Detective Agent AI service with CharacterAgent, LightRuleCheck, GameMasterAgent proposed events, spoiler-safe prompts, fallbacks, and observability.
version: 1.0.0
author: Team-8
license: MIT
metadata:
  hermes:
    tags: [ai-service, fastapi, langgraph, prompts, guardrails, observability, clean-code]
    related_skills: [codex]
---

# Detective Agent AI Skill

## Mission

Build the internal AI service that turns BE-approved facts into character dialogue, checks safety, proposes events, and explains hints/summaries/endings without owning game state.

## Must Preserve

- CharacterAgent -> LightRuleCheck -> GameMasterAgent order for dialogue.
- Output facts must stay within `allowedStatement` and visible/reveal-allowed data.
- AI never decides verdicts, unlocks, pressure, culprit, or phase.
- `proposedEvents[]` are suggestions only; BE validates and applies.
- Deterministic fallback must work without an external LLM key.

## Development Flow

1. Read `AGENTS.md`, `Docs/implementation.md`, `../PRD.md`, and `../Docs/structure-audit.md`.
2. Inspect request/response schemas before graph or prompt changes.
3. Keep prompt text in `app/prompts/*` and provider integration in `app/core/llm.py`.
4. Add tests for fallback, guard repair, spoiler prevention, and schema stability.
5. Run `pytest -q` before reporting done.

## Observability Checklist

- Log graph/node start/end with latency.
- Log provider/model and fallback status, never API keys or full hidden prompts.
- Log guard repairs and blocked reasons.
- Log proposed event count and event types, not secret content.
- Include `session_id`, `case_id`, `request_id` when available.

## Code Smell Guardrails

- No route-level prompt construction.
- No hidden case-data reads from filesystem during request handling.
- No broad fallback that hides schema errors silently.
- No global mutable per-session state.
- No generated text that adds new facts not present in allowed data.
