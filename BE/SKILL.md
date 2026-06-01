---
name: detective-agent-backend
description: Use when implementing the Detective Agent BE FastAPI service with deterministic rule engine, safe public payloads, event processing, SSE, clean code, and structured observability.
version: 1.0.0
author: Team-8
license: MIT
metadata:
  hermes:
    tags: [backend, fastapi, rule-engine, sse, observability, clean-code]
    related_skills: [codex]
---

# Detective Agent Backend Skill

## Mission

Build the Backend as the single source of truth for sessions, case visibility, deterministic rule verdicts, unlocks, event processing, and FE-facing contracts.

## Must Preserve

- Natural-language dialogue UI, internally mapped to case graph and allowed statements.
- AI is advisory: text + `proposedEvents[]`; BE validates state changes.
- Public payloads must never expose `secret`, `solution`, `isCulprit`, private motives, or hidden timeline entries.
- Same state and same submitted IDs must produce the same contradiction/accusation verdict.

## Development Flow

1. Read `AGENTS.md`, `Docs/implementation.md`, `../PRD.md`, and `../Docs/structure-audit.md`.
2. Inspect the route/schema/domain files touched by the requested change.
3. Update schemas first when contracts change.
4. Put rule logic in domain services, not routes.
5. Add/adjust tests for public payload secrecy, deterministic verdict, and event emission.
6. Run `pytest -q` before reporting done.

## Observability Checklist

- Request ID middleware exists or is introduced before broad logging.
- Logs include `service`, `request_id`, `session_id`, `case_id`, `route`, `duration_ms` where applicable.
- Rule decisions log verdict/reason codes, not secret solution text.
- AI fallback and rejected events are WARNING level.
- SSE replay/reconnect logs `last_event_id` and emitted event count.

## Code Smell Guardrails

- No route handler should perform deep case graph traversal inline.
- No duplicated hidden-field filtering across many endpoints; centralize view builders.
- No LLM-generated verdicts or unlocks.
- No broad `except Exception: pass`; fallback paths must log why.
- No tests that require special PYTHONPATH; plain `pytest -q` should pass.
