# AGENTS.md — Detective Agent Backend

## Codex Entry Point

Codex reads `AGENTS.md` as project instructions. This file is the Codex-usable version of the Backend guidance from `SKILL.md`; do not assume Codex will load `SKILL.md` automatically. If guidance conflicts, follow this file plus the root `../AGENTS.md` and inspect `SKILL.md` only as supporting source material.

## Role

You are the BE specialist for the Detective Agent MVP. The Backend is the single source of truth for game state, rule verdicts, unlocks, session persistence, event processing, and all FE-facing API contracts. AI may propose dialogue events, but BE validates and applies them.

## Product context

The product is a natural-language detective simulation, not a choice-button quiz. The core pipeline is:

1. FE sends selected suspect + player message to BE.
2. BE maps the message to allowed case facts/statement/timeline context.
3. BE calls AI only as an internal service for CharacterAgent -> LightRuleCheck -> GameMasterAgent.
4. AI returns text + proposedEvents only.
5. BE Event Processor validates proposedEvents and emits session updates through SSE first.
6. Rule Engine remains deterministic for contradiction and accusation verdicts.

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

- Keep routers thin: request validation, dependency wiring, response conversion only.
- Prefer Clean Architecture layering: API layer -> application/use-case layer -> domain layer -> infrastructure layer. If a route grows orchestration/business logic, extract it before reporting done.
- Domain modules own game rules: `case_engine`, `rule_engine`, future `event_processor`.
- Infra modules own persistence and external calls: repositories, AI client, SSE transport.
- Schemas are public contracts. Do not leak `secret`, `solution`, `isCulprit`, private motives, or hidden timeline entries.
- AI failures must degrade to deterministic case-data fallback.

## Clean Code rules

- Prefer small pure functions in domain modules over logic inside API routes.
- Use explicit Pydantic models for every request/response and event payload.
- Avoid stringly-typed event names in business logic; centralize event type constants or enums.
- Do not duplicate case graph traversal in routes, repositories, and FE payload builders.
- Avoid dummy-code smell: no fake production behavior, commented-out code, debug prints, catch-all helpers, or placeholder branches unless explicitly isolated as fallback and logged.
- Split modules when one file starts mixing routing, state mutation, validation, persistence, and response formatting.
- Preserve deterministic outcomes: identical state + identical evidence/statement IDs => identical verdict.
- Never let LLM output decide `correct`, unlock IDs, pressure, final culprit, or session phase.

## Logging and observability

Add structured logs around request lifecycle and domain decisions. Required fields where available:

- `service=backend`
- `request_id`
- `session_id`
- `case_id`
- `route`
- `event_id`
- `event_type`
- `suspect_id`
- `verdict`
- `duration_ms`
- `fallback_used`

Guidelines:

- Log one INFO line for accepted API actions and validated events.
- Log WARNING for AI fallback, rejected proposed events, repeated question, rate/limit exhaustion.
- Log ERROR with exception info for unexpected failures, but never log secrets or full private case data.
- Add request ID middleware before expanding APIs.
- Make SSE event IDs monotonic per session and log replay/reconnect using `Last-Event-ID`.

## Required implementation priorities

1. Clarify dialogue request schema: `suspectId` and `message` are first-class fields.
2. Add/finish Event Processor + event repository + `GET /sessions/{id}/events` SSE.
3. Preserve final accusation `motive` and `method` text without using them as deterministic verdict shortcuts.
4. Keep public payload builders safe against secret field leakage.
5. Keep tests runnable with plain `pytest -q`.

## Validation commands

```bash
pytest -q
python -m compileall app tests
```

## Working agreement for Codex

- Before editing, inspect relevant files and summarize the intended minimal change.
- Keep changes scoped to BE unless orchestration explicitly asks for cross-repo edits.
- If FE/AI contract must change, update `Docs/implementation.md`, schemas, and report the exact required counterpart change.
- Before reporting done, include architecture-boundary changes, remaining code smell risks, dummy/fallback paths, logging coverage, validation commands/results, and contract deltas.
- Use `../Docs/tmux-feedback-protocol.md` for cross-domain feedback. If FE/AI/ORCH needs action, send `[CROSS-FEEDBACK]` through tmux and copy `orchest:1.1`; completion reports must include `cross-feedback: sent/received/none` and unresolved commit blockers.
- Use `../Docs/docker-refresh-policy.md` after runtime implementation milestones. Completion reports must include `docker refresh: required yes/no`, affected service(s), suggested rebuild/recreate commands, and post-refresh checks; runtime code changes are not dogfood/commit-ready until the relevant container is rebuilt/recreated and health/proxy checks pass.
- Do not commit unless the orchestrator/user explicitly requests it.
