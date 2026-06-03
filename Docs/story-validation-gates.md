# Story Validation Gates

Owner: DOCS
Scope: manual/API/browser validation cases for story, dialogue, event, public/private, and visual contracts.

These gates are required before BE, embedded AI engine, and FE runtime work is considered MVP commit-ready. Docs-only changes can be commit-ready separately after markdown sanity checks.

## 1. Prerequisites

Expected service URLs when using Docker compose:
- FE: `http://127.0.0.1:8080`
- BE: `http://127.0.0.1:8000`

Suggested runtime refresh after BE/FE runtime code changes:

```bash
docker compose up -d --build backend frontend
```

Docs-only changes:
- Docker refresh required: no.

Production-like validation rule:
- BE/embedded-AI/FE runtime commit-ready requires Docker refresh after runtime changes, direct health checks, proxy health checks, real FE -> BE embedded AI smoke, SSE replay smoke, public leak scan, and explicit provider/fallback diagnostics.
- Mock/local/canned paths may be used for unit tests, but they do not satisfy production runtime commit-ready gates.

## 2. Public payload leak scan

Goal: public case/session/dialogue payloads must not leak private truth.

Forbidden strings/keys:
- `secret`
- `solution`
- `privateTimeline`
- `isCulprit`
- `culprit`
- `culpritId`
- `finalDiscovery`
- `finalVerdict`
- `privateRefs`
- `secretNote`
- `privateMotive`
- `privateEvents`
- `actualAction`
- `actualLocation` when private truth
- `culpritId` outside reveal/ending endpoints
- `solution_hidden_scene_manipulation`

API check:

```bash
curl -s http://127.0.0.1:8000/api/v1/cases/case_001 | jq . > /tmp/case_public.json
curl -s -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"caseId":"case_001"}' | tee /tmp/session_public.json | jq .
python - <<'PY'
import json, re
for path in ['/tmp/case_public.json', '/tmp/session_public.json']:
    text=open(path).read()
    bad=[k for k in ['secret','solution','privateTimeline','isCulprit','culprit','culpritId','finalDiscovery','finalVerdict','privateRefs','secretNote','privateMotive','privateEvents','actualAction','actualLocation','solution_hidden'] if re.search(k, text, re.I)]
    assert not bad, (path, bad)
print('leak scan passed')
PY
```

Acceptance:
- No forbidden key/string appears in public case/session payloads.
- Visible timeline excludes hidden timeline entries.
- Public clue paths exclude `secretNote`.

## 3. Greeting/small talk gate

Goal: greeting is not treated as a case fact.

API steps:

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"caseId":"case_001"}' | jq -r .sessionId)

curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/dialogue" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","message":"안녕하세요. 잠깐 이야기할 수 있을까요?"}' \
  | tee /tmp/dialogue_greeting.json | jq .dialogueResult

curl -N "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/events?once=true" > /tmp/events_greeting.txt
```

Acceptance:
- `dialogueResult.dialogueMode` or `intent` is `small_talk`/`greeting`.
- `dialogueResult.matchedQuestionId == null`.
- `dialogueResult.consumedQuestion == false`.
- `remainingQuestionsDelta == 0` and `remainingQuestions` unchanged.
- SSE/event replay contains no `NOTE_FACT_ADDED` caused by this greeting.
- FE shows `matched: null` and no new notebook fact.

## 4. Unmatched/evidence term gate: wine/hallway

Goal: unmatched or weakly related evidence terms must not jump to inheritance or a random first question.

API messages to test:
- `와인잔에 대해 설명해 주세요.`
- `복도에서 누굴 봤나요?`
- `hallway wine record?`

Acceptance:
- If no visible evidence/statement matches, `dialogueMode=unmatched` and `matchedQuestionId=null`.
- If visible evidence matches, `dialogueMode=evidence_question` and answer stays within visible evidence context.
- Must not match `q_hanseoyeon_inheritance` unless terms include inheritance/will conflict explicitly.
- No random first question is consumed.
- No `NOTE_FACT_ADDED` unless proposed event references stable visible IDs and BE validates it.

## 5. Alibi persona/timeline differentiation gate

Goal: same alibi-style question to Han Seo-yeon and Park Min-gyu produces character/timeline/persona-different answers.

API steps:

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"caseId":"case_001"}' | jq -r .sessionId)

for SUSPECT in char_hanseoyeon char_parkmingyu; do
  curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/dialogue" \
    -H 'Content-Type: application/json' \
    -d "{\"suspectId\":\"$SUSPECT\",\"message\":\"22시 이후 어디에 있었나요?\"}" \
    | tee "/tmp/alibi_$SUSPECT.json" | jq '{answer, dialogueResult, visualState}'
done
```

Acceptance:
- Han answer reflects her public persona/speech style and her own public timeline/allowed statement.
- Park answer reflects medical/professional persona and his own public timeline/allowed statement.
- Answers are not identical canned echoes except for allowed factual anchor when appropriate.
- `matchedQuestionId` differs by suspect or null behavior is explained by current unlock state.
- No private truth is revealed.

## 6. Tension variant gate

Goal: same suspect under low vs high tension changes wording and expression metadata.

Setup options:
- Use contradiction submission that raises pressure, or a test fixture/session state endpoint if available.
- For Han, submit `st_hanseoyeon_room_2200` + `ev_study_entry_log` to raise pressure.

API sketch:

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"caseId":"case_001"}' | jq -r .sessionId)

curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/dialogue" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","message":"22시 이후 어디에 있었나요?"}' \
  | tee /tmp/tension_low.json | jq '{answer, dialogueResult, visualState}'

curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/contradictions" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","statementIds":["st_hanseoyeon_room_2200"],"evidenceIds":["ev_study_entry_log"]}' \
  | jq '{contradictionResult, visualState, pressureBySuspect}'

curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/dialogue" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","message":"다시 묻겠습니다. 22시 이후 정말 방에만 있었습니까?"}' \
  | tee /tmp/tension_high.json | jq '{answer, dialogueResult, visualState}'
```

Acceptance:
- Low response has controlled/neutral wording and low/neutral visual state.
- High/medium response has defensive/shocked/angry/breakdown wording according to pressure threshold.
- `visualState.tensionLevel`, `visualState.expression`, `dialogueResult.emotionalState`, and suspect payload change consistently.
- FE portrait/background classes or assets change accordingly.
- The tension increase is caused by a BE-validated new contradiction discovery, not by generic dialogue or unlock-only events.

## 7. Contradiction candidate proposed event gate

Goal: evidence + statement conflict creates a BE-validated contradiction candidate note over SSE.

API steps:

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"caseId":"case_001"}' | jq -r .sessionId)

# Ensure relevant statement is unlocked if needed.
curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/dialogue" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","message":"22시 이후 어디에 있었나요?"}' > /tmp/pre_contradiction_dialogue.json

curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/dialogue" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","message":"당신의 방 알리바이와 서재 출입 기록이 충돌하는 것 아닌가요?"}' \
  | tee /tmp/contradiction_candidate_dialogue.json | jq '{dialogueResult, proposedEventsApplied, visualState}'

curl -N "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/events?once=true" > /tmp/events_contradiction.txt
```

Acceptance:
- AI may propose `NOTE_CONTRADICTION_CANDIDATE_ADDED`, but BE decides whether to apply.
- Applied SSE contains `NOTE_CONTRADICTION_CANDIDATE_ADDED` only when required `statementIds/evidenceIds` are visible/unlocked.
- Event payload contains stable `contradictionId`, `statementIds`, `evidenceIds`, optional `timelineIds`, `noteId`, and sanitized display text.
- FE displays contradiction candidate as candidate until player submits it; it is not automatically final truth.

## 8. Direct contradiction submit gate

Goal: explicit contradiction submission is deterministic and BE-owned.

API:

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/contradictions" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","statementIds":["st_hanseoyeon_room_2200"],"evidenceIds":["ev_study_entry_log"]}' \
  | tee /tmp/contradiction_submit.json | jq '{contradictionResult, currentActId, currentObjective, pressureBySuspect, newlyUnlockedIds, visualState}'
```

Acceptance:
- `contradictionResult.verdict == correct` or equivalent current BE verdict field.
- `discoveredContradictionIds` includes `con_room_claim_vs_entry_log`.
- pressure increases for Han.
- current objective/act advances according to `currentObjectiveRules`.
- SSE includes relevant note/tension/visual events.
- `TENSION_CHANGED` appears exactly once for the first successful discovery of this contradiction.
- Re-submitting the same statement/evidence contradiction does not increase pressure again and does not emit a second effective `TENSION_CHANGED`.

## 9. BE -> AI payload contract gate

Goal: AI receives canonical public-only story context.

Validation method:
- Use BE structured logs or a test double AI endpoint to capture `/internal/v1/dialogue/respond` payload.

Acceptance:
- Payload contains `suspect.publicPersona`, `speechStyle`, `publicTimeline`, `pressure`, `tensionLevel` label, optional `tensionScore`, `emotionalState`.
- Payload contains `currentActId`, `currentObjective`, `visibleFacts`, `dialogueHistorySummary`, `allowedStatement`, `revealAllowed=false`, `allowedEventPolicy`.
- Payload contains public-only `characterKnowledgePack` with `personaVariants`, selected `activePersonaOverlay`, visible timeline/alibi/evidence/relationship snippets, recent dialogue, and `forbiddenRefs`.
- Payload contains no forbidden private fields.
- `suspect.tensionLevel` is label string; AI schema accepts it.

## 10. 3-Agent schema and persona injection gate

Goal: AI implements the first-class model in `Docs/story-agent-contract.md`, not loose helper functions or vague graph labels.

Acceptance:
- AI has typed/validated equivalents for `CharacterAgentInput`, `DraftCharacterReply`, `LightRuleCheckInput`, `CheckedCharacterReply`, `GameMasterAgentInput`, and `GameMasterProposal`.
- `CharacterAgentInput` consumes `CharacterKnowledgePack` plus `personaVariants` and `activePersonaOverlay`.
- `DraftCharacterReply` includes draft text, used/source refs, voice metadata, persona overlay ID, provider/model, fallback/degraded metadata, and no proposed events.
- `LightRuleCheck` validates/repairs/blocks text and returns safety findings; it has no state mutation or proposed event output.
- `GameMasterProposal` contains `proposedEvents[]` only and invariant flags proving no `TENSION_CHANGED`, no final verdict/discovery, no private reveal, and no BE mutation.
- Normal/baseline vs high/critical active persona overlays produce distinct voice/evasiveness/hesitation for the same allowed statement without changing facts.
- CaseWiki/Obsidian frontmatter examples compile to public `CharacterKnowledgePack` without forbidden private keys.
- Forbidden refs `secret`, `solution`, `privateTimeline`, `privateEvents`, `privateMotive`, `privateRefs`, `culprit`, `culpritId`, `isCulprit`, `finalDiscovery`, `finalVerdict`, `actualAction`, `actualLocation`, and `secretNote` are absent from `CharacterKnowledgePack`, AI logs, agent outputs, BE public payloads, SSE, and FE diagnostics.
- BE remains authority for visibility gates, EventProcessor validation, TensionPolicy, final contradiction state, persistence, and SSE.

## 11. Browser dogfood gate

Browser flow:
1. Open `http://127.0.0.1:8080`.
2. Confirm dark noir single-screen layout with suspect cards, central interrogation stage/input, evidence grid, contradiction panel, bottom system-flow strip.
3. Confirm runtime diagnostics show API vs LOCAL, provider, fallback/safety, matched question, event counts, last event ID.
4. Ask greeting and confirm no question decrement/new note.
5. Ask Han and Park alibi questions and compare answers.
6. Trigger contradiction and confirm visual/tension changes.
7. Confirm every player question and suspect answer appears as a separate named speaker bubble in the main dialogue view.
8. Open case file, evidence, notes, relationship map, and contradiction views/panels.
9. Watch console/network for API/SSE errors.

Acceptance:
- No structure-only UI regression.
- Natural-language input is the primary flow, not button-only choice mapping.
- FE clearly marks local fallback if BE/AI unavailable.
- SSE/network failures are visible in diagnostics and do not silently fake production truth.
- Per-turn dialogue bubbles are the primary conversation UX; no answer-only main panel with duplicated lower log.

## 12. Investigation read model browser gate

Goal: case file, evidence, relationship map, notebook/notes, and contradictions are queryable BE-backed gameplay surfaces.

Browser flow:
1. Open `http://127.0.0.1:8080`.
2. Click `사건 파일` and confirm opening/objective/rules/current act/visible timeline are populated from BE.
3. Click `증거 목록` or an evidence card and confirm a detail drawer/panel shows description, foundAt, timeWindow, reliability, source refs, and public lock/unlock state.
4. Click `인물 관계도` and confirm a populated map/panel renders BE `relationMap.nodes[]` and `relationMap.edges[]` with labels/descriptions.
5. Click `메모`, create a note linked to at least one evidence or statement if UI supports links, and confirm it persists after refresh or `GET /sessions/{sessionId}`.
6. Confirm notes create/update/delete behavior matches BE-supported scope and SSE or session refresh updates the UI.

API smoke:

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"caseId":"case_001"}' | jq -r .sessionId)

curl -s "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID" \
  | jq '{caseFile, relationMap, notebook, evidence, statements, contradictions, notes}'

curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/notes" \
  -H 'Content-Type: application/json' \
  -d '{"text":"dogfood note","linkedEvidenceIds":["ev_study_entry_log"],"linkedStatementIds":["st_hanseoyeon_room_2200"]}' \
  | jq .

curl -N "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/events?once=true" > /tmp/events_notes.txt
```

Acceptance:
- Public session payload includes `caseFile`, `relationMap`, `notebook`, evidence detail fields, statement/testimony records, public contradiction details, and notes.
- Relationship map opens and is not a dead control.
- Notes are BE-persisted and survive session refresh; LOCAL-only notes are a blocker.
- Evidence detail is inspectable and sufficiently detailed for cross-examination.
- Console/network show no API/SSE errors or asset 404s in normal Docker path.

## 13. Contradiction selection browser gate

Goal: contradiction gameplay requires player selection of testimony/statement plus evidence.

Browser flow:
1. Ask Han Seo-yeon for her alibi to unlock `st_hanseoyeon_room_2200`.
2. Ask a natural-language follow-up that explicitly mentions the public evidence, e.g. `서재 출입 기록에는 왜 당신 이름이 남아 있나요?`.
3. Confirm BE Dialogue API maps the utterance to public evidence/statement refs.
4. Confirm GameMaster proposedEvents and BE EventProcessor/SSE update contradiction detail, notes/notebook, pressure/tension, current objective, and visual state.

Acceptance:
- FE does not expose a canned `증거 제시` action that bypasses natural-language interrogation.
- BE validates public refs inferred from the dialogue turn and returns deterministic state updates.
- Candidate contradictions remain candidates until the dialogue pipeline and EventProcessor validate them.
- Discovered contradiction details are visible without FE inferring from IDs alone.

## 14. Comic/ImageGen asset gate

Goal: FE uses coherent noir comic/cartoon assets that support character-first interrogation.

Browser flow:
1. Open `http://127.0.0.1:8080`.
2. Inspect each suspect portrait and central character stage.
3. Ask dialogue and trigger a contradiction/tension change.
4. Inspect evidence cards and evidence detail drawer.
5. Check browser network/console for image 404s or fallback warnings.

Acceptance:
- Suspect portraits are coherent noir comic/cartoon assets, not placeholder-looking SVGs or generic avatars.
- At least neutral fallback exists for every suspect.
- Expressions referenced by canonical `tensionProfile` and runtime `visualState.expression` resolve to assets or documented neutral fallback.
- Dialogue/contradiction changes visibly update expression where BE state changes.
- Evidence cards show recognizable object/record art that supports inspection.
- No broken image URLs or silent asset fallback in normal Docker path.

## 15. Production BE/AI runtime smoke gate

Goal: prove the production-like path is not mock/canned/local-fallback based.

Required after BE or AI runtime changes:

```bash
docker compose up -d --build ai backend frontend
docker compose ps

curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:8080/api/v1/health || true
```

Dialogue smoke:

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"caseId":"case_001"}' | jq -r .sessionId)

curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/dialogue" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","message":"안녕하세요. 잠깐 이야기할 수 있을까요?"}' \
  | tee /tmp/prod_greeting.json | jq '{dialogueResult, provider, model, fallbackUsed, degraded, lastEventId}'

curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/dialogue" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","message":"서재 출입 기록을 설명해 주세요."}' \
  | tee /tmp/prod_evidence_question.json | jq '{answer, dialogueResult, proposedEventsCount, appliedEventsCount, lastEventId}'

curl -N "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/events?once=true" > /tmp/prod_events.txt
```

Acceptance:
- Dialogue path reports API source, real provider/model or explicitly approved production adapter, `fallbackUsed=false` for normal smoke.
- No `source=LOCAL`, mock provider, canned-only response, or silent fallback in normal production-like smoke.
- Greeting does not consume question or create fact note.
- Evidence question can produce canonical contradiction candidate when visible/unlocked policy allows it.
- SSE replay contains only BE-validated public events.
- Completion report includes exact Docker refresh, health/proxy, API, SSE, and log inspection commands.

## 16. AI failure/degraded semantics gate

Goal: embedded AI/provider failure does not fabricate detective progress.

Validation methods:
- Disable provider config in a controlled test profile, or use a test that simulates embedded AI timeout/error.
- Restore normal config after the test.

Acceptance:
- BE returns explicit failure or degraded response with `fallbackUsed=true` or `degraded=true`.
- Question count is not decremented unless documented as a failed attempt.
- No `NOTE_FACT_ADDED`, contradiction candidate, evidence unlock, tension progress, or objective advancement is created from AI failure.
- FE diagnostics show degraded/API failure state instead of normal-looking character testimony.
- Logs include `correlationId`/`requestId`, provider/fallback metadata, and no private story leakage.

## 17. TensionPolicy idempotency gate

Goal: BE owns monotonic/idempotent tension updates, and embedded GameMaster cannot fabricate them.

Required BE tests:
- Unlock-only event does not emit `TENSION_CHANGED` and does not change pressure.
- First validated evidence + testimony/alibi contradiction emits exactly one `TENSION_CHANGED` for the suspect.
- Duplicate proposed contradiction candidate, repeated question, SSE replay, or repeated direct contradiction submit does not increment pressure again.
- AI-down/degraded dialogue creates no unlock progress, no contradiction discovery, and no `TENSION_CHANGED`.

API sketch:

```bash
SESSION_ID=$(curl -s -X POST http://127.0.0.1:8000/api/v1/sessions \
  -H 'Content-Type: application/json' \
  -d '{"caseId":"case_001"}' | jq -r .sessionId)

# Unlock statement only.
curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/dialogue" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","message":"22시 이후 어디에 있었나요?"}' > /tmp/unlock_only.json
curl -N "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/events?once=true" > /tmp/unlock_only_events.txt

# First contradiction.
curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/contradictions" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","statementIds":["st_hanseoyeon_room_2200"],"evidenceIds":["ev_study_entry_log"]}' > /tmp/contradiction_first.json
curl -N "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/events?once=true" > /tmp/contradiction_first_events.txt

# Duplicate contradiction.
curl -s -X POST "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/contradictions" \
  -H 'Content-Type: application/json' \
  -d '{"suspectId":"char_hanseoyeon","statementIds":["st_hanseoyeon_room_2200"],"evidenceIds":["ev_study_entry_log"]}' > /tmp/contradiction_duplicate.json
curl -N "http://127.0.0.1:8000/api/v1/sessions/$SESSION_ID/events?once=true" > /tmp/contradiction_duplicate_events.txt
```

Acceptance:
- `/tmp/unlock_only_events.txt` contains no effective `TENSION_CHANGED`.
- First contradiction response/events contain one effective `TENSION_CHANGED` with `contradictionId`, `previousPressure`, `pressureDelta`, and new `pressure`.
- Duplicate response/events do not increase pressure and do not create a second effective tension increment.
- AI proposed events containing `TENSION_CHANGED`, if received, are rejected and logged as invalid.
- FE consumes only BE/SSE/session tension fields; FE does not derive pressure locally from dialogue or unlocks.

## 18. Observability and SSE replay gate

Goal: cross-service diagnostics are sufficient to debug production runtime.

Acceptance:
- BE logs include `correlationId`, `requestId`, `sessionId`, route, duration, provider/fallback metadata, proposed/applied/rejected event counts, and `lastEventId`.
- AI logs include `requestId`/`correlationId`, selected agent stage, provider/model, safety outcome, repair/block state, and proposed event count.
- FE diagnostics expose source API vs LOCAL, provider/model/fallback/degraded, matched question, event counts, and last event ID.
- SSE replay with `Last-Event-ID` returns deterministic events and logs requested/replayed IDs.
- Health/readiness checks distinguish service up from dependency/provider readiness where feasible.

## 19. Knowledge wiki authoring/lint gate

Goal: enrich case knowledge without breaking public/private boundaries or turning rules into dialogue scripts.

Docs/content lint acceptance:
- all wikilinks and stable IDs resolve
- no duplicate `factId`, `evidenceId`, `relationshipId`, `timelineId`, or `contradictionId`
- no orphan evidence without provenance/source refs
- no contradiction without statement/evidence/timeline refs
- no relationship edge with missing character endpoints
- no character knows impossible facts before visibility/unlock gates
- no `hidden_truth`, private timeline, culprit/final discovery, or solution-only note exports into public `CharacterKnowledgePack`
- all evidence has `whoKnows`, `whoCanInterpret`, provenance, visibility gate, and related refs
- all character pages define or explicitly empty witnessed/heard/believed/doubted/hidden/unknown/misbelieved facts
- all relationship edges separate public face from private truth
- all timeline events declare a layer: `global_truth`, `global_public`, `character_perceived`, `rumor`, `evidence_discovery`, or `contradiction_surfacing`
- all rumors include source and confidence

Runtime projection acceptance:
- player free-form question selects visible fact/evidence/relationship/timeline snippets deterministically
- `CharacterKnowledgePack` includes social/knowledge context but excludes private refs
- `CharacterAgent` answers autonomously from bounded context
- `LightRuleCheck` flags only impossible/leaky/inconsistent claims
- `GameMasterAgent` proposes public candidate/unlock events
- BE `EventProcessor` validates visibility, dedupe, mutation, final state, and SSE

Commit impact:
- This is a high-priority story/content architecture quality milestone.
- It does not invalidate already-passed no-mock/runtime gates by itself.
- Runtime commit-ready changes only when BE/embedded-AI/FE code or public contract fields change.

## 20. Markdown/docs validation gate

For DOCS-only changes:

```bash
python - <<'PY'
from pathlib import Path
paths = [
  'Docs/story-architecture.md',
  'Docs/story-agent-contract.md',
  'Docs/story-knowledge-wiki-contract.md',
  'Docs/story-data-contract.md',
  'Docs/service-contract-dialogue-story.md',
  'Docs/story-validation-gates.md',
  'Docs/Senario/schema.md',
]
for p in paths:
    path=Path(p)
    assert path.exists(), f'missing {p}'
    text=path.read_text()
    assert text.strip(), f'empty {p}'
    # Mermaid fence sanity is checked separately by scanning fenced blocks.
print('docs exist and are non-empty')
PY
```

Mermaid sanity:
- Every Mermaid block must start with a known diagram keyword: `flowchart`, `sequenceDiagram`, `classDiagram`, `stateDiagram`, or `erDiagram`.
- Markdown links to local files should use exact relative paths where possible.

## 21. Commit readiness checklist

Docs-only atomic commit can be ready when:
- Files exist and are non-empty.
- Mermaid fences are syntactically reasonable.
- Cross-feedback from BE/embedded-AI/FE is answered or recorded as known limitation/migration item.
- No runtime code changed.
- Docker refresh marked not required.

Overall MVP remains blocked until:
- Production-like BE embedded-AI smoke passes with no silent mock/canned/local fallback.
- Embedded AI failure/degraded semantics prove no fabricated progress on provider failure.
- TensionPolicy idempotency tests pass: unlock no tension, first contradiction exactly one tension change, duplicate no increment, AI-down no progress.
- Observability/SSE replay diagnostics pass.
- BE target schema/payload migration validated.
- First-class 3-Agent schemas and tension-level persona injection validated against `Docs/story-agent-contract.md`.
- Knowledge wiki authoring/lint gate passes when the case is enriched through `Docs/story-knowledge-wiki-contract.md`.
- AI schema/grounding/proposed event migration validated.
- FE visual/SSE/diagnostic contract migration validated.
- FE per-turn dialogue bubble UX passes browser dogfood.
- BE/FE investigation read models pass case/evidence/notes/relation/contradiction browser and API dogfood.
- FE ImageGen-grade noir comic character/evidence assets pass asset gate.
- Browser dogfood passes without runtime blockers.
