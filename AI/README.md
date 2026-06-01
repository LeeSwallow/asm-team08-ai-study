# Detective Agent AI Service

FastAPI + optional LangGraph based internal AI service for the conversational alibi cross-checking detective game.

The service does not judge final correctness or mutate game state. Its core dialogue pipeline is CharacterAgent → LightRuleCheck → GameMasterAgent: generate an in-character reply, verify abnormal/unsafe character output, then return proposed events for surfaced information. Backend Rule Engine/Event Processor remains authoritative for contradiction verdicts, event application, and SSE/WebSocket delivery.

## Endpoints

- `GET /health`
- `POST /internal/v1/dialogue/respond` — CharacterAgent reply + LightRuleCheck validation + GameMasterAgent proposed events
- `POST /internal/v1/hints`
- `POST /internal/v1/notes/summary`
- `POST /internal/v1/endings/explain`

## Run

```bash
cd AI
uv sync
uv run uvicorn app.main:app --reload --port 8001
```

LangGraph is optional at runtime. If it is installed, graph workflows run through LangGraph. If it is missing or unavailable, the same node sequence runs through the deterministic fallback pipeline.

Production-like runs should set `AI_LLM_PROVIDER=openai`, `AI_OPENAI_API_KEY`, and `AI_MODEL_NAME`. The default `AI_LLM_PROVIDER=fallback` is an explicit deterministic degraded mode for local development and tests; responses expose `fallbackUsed`, `serviceDegraded`, and `blockedReason` metadata so Backend can avoid treating degraded output as normal provider-backed progress.

## Docker

```bash
cd AI
docker build -t detective-ai-service .
docker run --rm -p 8001:8001 detective-ai-service
```

The container starts:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Safety Rules

- Dialogue output is scoped to backend-approved case facts/allowed statements, even when the player enters free-form text.
- CharacterAgent may add only whitelisted non-factual tone/emotion padding around backend-approved content.
- Culprit, motive, weapon, and solution terms are redacted unless `revealAllowed` is true.
- Ending explanations preserve the backend verdict and never recompute correctness.
- GameMasterAgent proposed events use only supplied dialogue logs, discovered evidence, allowed event policy, and validated surfaced facts.
- Every response includes `safety.fallbackUsed`, `safety.repaired`, and `safety.blockedReason` so Backend can log provider fallback or guard repairs.

## Backend Contract

The Backend remains the single source of truth for rule results, pressure changes, unlocks, question counts, and final correctness. This service only receives backend-approved inputs and returns natural-language text, validation metadata, optional `proposedEvents[]`, and a `safety` object. If the configured LLM provider is unavailable or raises, `/internal/v1/dialogue/respond` returns explicit degraded fallback metadata and suppresses proposed events so Backend does not apply fabricated progress.

`Hint`, `Summary`, and `Ending` generation ignore unknown extra fields. They render only whitelisted request fields:

- Storyline context: optional `storyline.currentObjective`, `storyline.currentActId`, `storyline.visibleTimeline`, `storyline.publicPremise`, `storyline.openingObjective`
- Dialogue: `allowedStatement.text` remains the only factual content; storyline/visualState may adjust tone and emotion only
- Hint: `allowedClues`, public storyline context, `discoveredEvidence.id/name`, `hintLevel`, `revealAllowed`
- Summary: public storyline context, `dialogueLogs.speaker/text/id/statementId`, `discoveredEvidence.id/name/description`, `maxItems`, `revealAllowed`
- Ending: public storyline context, `verdict.result/label/reason/missedEvidenceIds/revealAllowed`, `culpritName` only when reveal is allowed, and supplied result counts

Unknown or secret-oriented fields such as `secret`, `solution`, `isCulprit`, and `secretNote` are ignored by renderers. If a hidden timeline item is accidentally included with `hidden=true`, hint and summary generation skip it.

## Verify

```bash
uv run python -m compileall app
uv run pytest -q
docker build -t detective-ai-service .
```
