# Architecture & Quality Gates — Detective Agent

This document is the shared quality bar for BE, FE, and AI agents. It is mandatory for all new implementation and refactoring work.

## Non-negotiable principles

1. Clean Architecture first
   - Separate presentation/API, application/use-case, domain, and infrastructure concerns.
   - Business rules must not live in route handlers, React page monoliths, or LLM/provider adapters.
   - Cross-boundary data must use explicit typed schemas/contracts.

2. Component/module decomposition
   - Split large files before they become dumping grounds.
   - Prefer small components/functions with one reason to change.
   - Avoid god objects, mega components, catch-all helpers, and duplicated mapping logic.

3. No dummy-code smell
   - Do not leave placeholder behavior pretending to be production behavior.
   - Mock/fallback code must be explicitly named as fallback, isolated, and logged.
   - Remove commented-out code, unused branches, dead props, fake TODO implementations, and console/debug prints.

4. Observable by design
   - Logging must be centralized behind a small utility/module per repo.
   - Logs must be structured and include correlation fields where available.
   - Never log secrets, full hidden case data, API keys, or full player free text by default.

5. Validation before done
   - Each agent completion report must include changed files, validation commands/results, remaining code smell risk, and contract deltas.

## Layering expectations

### Backend

Expected direction:

- API layer: FastAPI routes, dependency injection, request/response conversion only.
- Application/use-case layer: session commands, dialogue orchestration, event processing coordination.
- Domain layer: case rules, verdicts, event validation, pressure/timeline/notebook logic.
- Infrastructure layer: repositories, AI client, persistence, SSE transport, logging adapters.

Forbidden smells:

- Route handlers directly mutating complex session state.
- LLM response trusted as authority for unlocks/verdicts/state transitions.
- Stringly-typed event handling scattered across files.
- Persistence format knowledge leaking into domain rules.

### Frontend

Expected direction:

- Page/container layer: orchestration and screen-level data flow.
- Feature components: suspect list, interrogation stage, evidence grid, contradiction panel, system flow strip.
- Hooks/services: API calls, SSE subscription, session persistence, reducers.
- View models/adapters: convert BE payloads to UI-ready props.
- Shared utilities: logging, formatting, accessibility helpers.

Forbidden smells:

- One huge `App.tsx` owning all rendering, state transitions, API calls, and mapping logic.
- Local fake truth that disagrees with BE state.
- Inline duplicated ID/status mapping across components.
- Visual parity achieved by brittle hard-coded data instead of typed view models.

### AI service

Expected direction:

- Route layer: schema validation and response conversion only.
- Application/graph layer: CharacterAgent -> LightRuleCheck -> GameMasterAgent orchestration.
- Domain/safety layer: guard rules, allowed-event policy enforcement, redaction/repair.
- Infrastructure layer: LLM provider client, prompt loading/versioning, logging.
- Prompts: versioned files/modules, not buried inside route handlers.

Forbidden smells:

- Provider code mixed into graph/domain logic.
- Hidden truth used when `revealAllowed=false`.
- AI mutating or deciding authoritative game state.
- Global mutable per-session state.

## Observability contract

Minimum correlation fields:

- `service`
- `request_id` or `requestId`
- `session_id` or `sessionId`
- `case_id` or `caseId`
- operation/action name
- duration/latency in ms where meaningful
- fallback/repair status where meaningful

Event-specific fields:

- Backend: `route`, `event_id`, `event_type`, `suspect_id`, `verdict`, `fallback_used`.
- Frontend: `component`, `action`, `eventId`, `eventType`, `suspectId`, `connectionState`, `durationMs`.
- AI: `graph`, `node`, `provider`, `model`, `latency_ms`, `fallback_used`, `repaired`, `blocked_reason`, `proposed_event_count`.

## Completion checklist for every agent

Before reporting done, each BE/FE/AI agent must answer:

1. Which files changed?
2. Which architecture boundaries were preserved or improved?
3. Which large files/components were split or intentionally left as-is and why?
4. Which dummy/mock/fallback paths remain, and are they isolated/logged?
5. Which validation commands passed or failed?
6. What contract changes are required from the other repos?
7. What code smell risk remains?

## Refactoring priority

If implementation and clean architecture conflict, do the minimal user-visible implementation first only when needed to preserve progress, then immediately refactor within the same task before reporting done. Do not let MVP speed become permanent architecture debt.
