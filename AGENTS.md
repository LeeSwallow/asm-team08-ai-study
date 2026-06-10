# AGENTS.md — Detective Agent Root Codex Context

## Purpose

Codex reads `AGENTS.md` as project instructions. The Hermes-style `SKILL.md` files in this repository are not guaranteed to be loaded by Codex automatically, so their operational guidance is exposed here and in subdirectory `AGENTS.md` files.

When working in a subdirectory, also obey the nearest nested `AGENTS.md`:

- `BE/AGENTS.md` for Backend work.
- `FE/AGENTS.md` for Frontend work.
- `story-generator-workflow/AGENTS.md` for case-generation workflow work.

## Product Direction

Detective Agent is a natural-language alibi cross-checking detective simulation MVP, not a choice-button quiz.

Core runtime path:

```text
Player natural-language question
-> FE investigation desk
-> BE session/dialogue API
-> BE embedded AI pipeline
   CharacterAgent -> LightRuleCheck -> GameMasterAgent(proposedEvents)
-> BE Event Processor validates/applies state changes
-> SSE/session payload updates FE
```

Hard boundaries:

- BE is the source of truth for sessions, state changes, unlocks, contradiction verdicts, accusation verdicts, and public payload filtering.
- AI may generate suspect dialogue and propose events, but deterministic BE validation decides whether state changes are applied.
- FE reflects BE session truth and SSE events; it must not infer or store hidden culprit/solution truth.
- Public payloads, logs, prompts, fixtures, and UI must not leak `secret`, `solution`, `isCulprit`, hidden truth, private motives, private timelines, culprit-only method/motive, or hidden timeline entries.

## Repository Map

- `BE/`: FastAPI backend, deterministic rule engine, session/event API, embedded AI engine, tests.
- `FE/`: React/Vite frontend investigation desk, BE API client, SSE consumer, assets.
- `Docs/`: product, scenario, architecture, service/story contracts, orchestration, quality gates.
- `story-generator-workflow/`: authoring workflow that converts source stories into playable Detective Agent case packages.
- `docker-compose.yml`: local FE/BE/PostgreSQL/Neo4j runtime.

Primary root references:

- `README.md`
- `PRD.md`
- `Docs/structure-audit.md`
- `Docs/architecture-quality-gates.md`
- `Docs/docker-refresh-policy.md`
- `Docs/tmux-feedback-protocol.md`
- `Docs/codex-orchestration.md`
- `Docs/story-data-contract.md`
- `Docs/service-contract-dialogue-story.md`

## Global Development Rules

1. Keep changes scoped to the requested area. Do not perform broad rewrites or cleanup unrelated files.
2. Preserve natural-language interrogation as the main gameplay surface.
3. Prefer bounded generative autonomy over guard/replace accretion: improve case data, CaseWiki/persona/seed/prompt contracts, and agent-output contracts before adding brittle deterministic dialogue replacements.
4. Keep route/component files thin; move business logic into domain/application services or focused hooks/adapters.
5. Treat fallback/mock paths as visible fallback behavior, not as silent fake production success.
6. Add or update tests/docs when API contracts, events, case data schema, or runtime behavior changes.
7. Never commit unless the user/orchestrator explicitly asks.

## Runtime and Docker Validation Policy

After BE/FE/AI runtime milestones, rebuild/recreate affected Docker Compose services before dogfood or commit-ready reporting. Completion reports must include:

- `docker refresh: required yes/no`
- affected service(s)
- reason
- command(s) run or suggested
- health/proxy checks and results

Typical checks:

```bash
docker compose up --build
curl -f http://127.0.0.1:8000/api/v1/health
curl -I http://127.0.0.1:8080/
```

Targeted tests alone are not enough to call a runtime change dogfood-ready.

## Validation Commands

Backend:

```bash
cd BE && pytest -q
cd BE && python -m compileall app tests
```

Frontend:

```bash
cd FE && npm run build
```

Root frontend build alias, if package scripts are configured:

```bash
npm run build
```

Story workflow validation depends on the changed area, but must at minimum include the workflow script help/compile path and generated artifact validation when output schemas change.

## Cross-Domain Feedback Protocol

Use `Docs/tmux-feedback-protocol.md` when a BE/FE/Docs/AI contract change requires another domain to act.

If cross-domain action is needed:

- send `[CROSS-FEEDBACK]` through tmux according to the protocol,
- copy `orchest:1.1`,
- report sent/received/blockers.

Completion reports must include `cross-feedback: sent/received/none`.

## Completion Report Required Shape

When reporting done, include:

- files changed
- validation commands and real results
- docker refresh requirement and affected services
- public contract deltas, if any
- fallback/mock paths touched, if any
- observability/logging coverage, if relevant
- cross-feedback status
- unresolved blockers or known exclusions
