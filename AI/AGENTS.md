# AGENTS.md — Detective Agent AI Service

## Role

You are the AI specialist for the Detective Agent MVP. The AI service is internal-only and supports narrative generation, safety checking, hinting, note summaries, and ending explanation. It does not own game state or verdict authority.

## Product context

The required pipeline for dialogue is CharacterAgent -> LightRuleCheck -> GameMasterAgent.

- CharacterAgent rewrites BE-approved statements in character voice.
- LightRuleCheck verifies no solution leak, no case-fact violation, no tone/visual mismatch.
- GameMasterAgent returns `proposedEvents[]` only; BE validates and applies them.

Primary references:
- `../PRD.md`
- `../Docs/structure-audit.md`
- `../Docs/architecture-quality-gates.md`
- `../Docs/tmux-feedback-protocol.md`
- `../Docs/docker-refresh-policy.md`
- `Docs/implementation.md`
- `SKILL.md`
- `Docs/commit-convention.md`

## Architecture boundaries

- AI never reads BE databases or case JSON directly during requests; use only payload data from BE.
- AI never mutates session state, unlocks evidence, changes pressure, or decides final verdict.
- `secret`, `solution`, `isCulprit`, hidden timeline/private fields must be ignored if accidentally supplied.
- LLM provider usage must be isolated behind `app/core/llm.py` and deterministic fallback must always work.
- Preserve Clean Architecture layering: route/schema conversion -> graph/application orchestration -> safety/domain policy -> provider/prompt/logging infrastructure.

## Clean Code rules

- Keep graph nodes small and testable: load context, generate, check, propose, format.
- Keep prompts versioned in `app/prompts/*`; do not bury prompt text in route handlers.
- Use Pydantic schemas for all internal request/response contracts.
- Make safety metadata explicit: `fallbackUsed`, `repaired`, `blockedReason`, `leaksSolution`, `violatesCaseFacts`.
- Prefer conservative repair/fallback over creative expansion when allowed data is insufficient.
- Do not introduce global mutable state for per-session context.
- Avoid dummy-code smell: no fake provider behavior masquerading as production, no prompts buried in route handlers, no debug prints, no unused placeholder branches. Deterministic fallback must be explicit, tested, and logged.
- Split graph/policy/provider code when one module starts mixing request parsing, generation, safety validation, proposed-event policy, and response formatting.

## Logging and observability

Add structured logs around graph execution and provider calls.

Required fields where available:

- `service=ai`
- `request_id`
- `session_id`
- `case_id`
- `graph`
- `node`
- `provider`
- `model`
- `latency_ms`
- `fallback_used`
- `repaired`
- `blocked_reason`
- `proposed_event_count`

Guidelines:

- INFO: graph start/end, node success, fallback selected intentionally.
- WARN: guard repair, ignored unsafe/hidden extra field, provider timeout/fallback.
- ERROR: schema-invalid graph output, unexpected provider exception.
- Never log hidden case facts, solution, API keys, or full prompts containing private data.
- Log prompt/template version and allowed statement ID, not full secret context.

## Required implementation priorities

1. Ensure dialogue response always includes safe answer text, safety metadata, visualState, and proposedEvents list.
2. Make `violatesCaseFacts` reflect the final emitted text after repair, not only the first LLM draft.
3. Expand GameMasterAgent proposed events only within BE-provided allowed policy.
4. Keep hint/summary/ending spoiler-safe using `revealAllowed` and visible timeline only.
5. Keep tests runnable with plain `pytest -q`.

## Validation commands

```bash
pytest -q
python -m compileall app tests
```

## Working agreement for Codex

- Before editing, inspect schemas, graph node flow, prompts, and tests for the target endpoint.
- Keep changes scoped to AI unless orchestration explicitly asks for cross-repo edits.
- If BE payload lacks fields required for safe generation, report the exact schema addition instead of guessing hidden truth.
- Before reporting done, include architecture-boundary changes, remaining code smell risks, fallback paths, structured logging coverage, validation commands/results, and BE contract deltas.
- Use `../Docs/tmux-feedback-protocol.md` for cross-domain feedback. If BE/FE/ORCH needs action, send `[CROSS-FEEDBACK]` through tmux and copy `orchest:1.1`; completion reports must include `cross-feedback: sent/received/none` and unresolved commit blockers.
- Use `../Docs/docker-refresh-policy.md` after runtime implementation milestones. Completion reports must include `docker refresh: required yes/no`, affected service(s), suggested rebuild/recreate commands, and post-refresh checks; AI runtime changes are not integration-dogfood/commit-ready until the AI container is rebuilt/recreated and AI/BE health checks pass.
- Do not commit unless the orchestrator/user explicitly requests it.
