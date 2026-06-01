# Service Contract: Dialogue Story Flow

Owner: DOCS
Scope: canonical BE <-> AI <-> FE contracts for story-grounded dialogue, diagnostics, visual state, proposed events, and public session payloads.

The first-class AI agent schema contract lives in `Docs/story-agent-contract.md`. This service contract embeds the same fields at the BE <-> AI boundary.

## 1. Endpoint overview

FE -> BE:
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{sessionId}`
- `POST /api/v1/sessions/{sessionId}/dialogue`
- `GET /api/v1/sessions/{sessionId}/events` (SSE)
- `POST /api/v1/sessions/{sessionId}/contradictions`
- `GET /api/v1/sessions/{sessionId}/notes`
- `POST /api/v1/sessions/{sessionId}/notes`
- `PUT /api/v1/sessions/{sessionId}/notes/{noteId}` when update is supported
- `DELETE /api/v1/sessions/{sessionId}/notes/{noteId}` when delete is supported

BE -> AI:
- `POST /internal/v1/dialogue/respond`

Authoritative state mutation:
- Only BE `EventProcessor`, `RuleEngine`, and session commands mutate session state.
- AI returns `proposedEvents[]` only.
- FE displays state and sends player actions only.

Production runtime requirement:
- Production-like dogfood must exercise FE -> BE -> AI -> BE EventProcessor -> SSE -> FE panels.
- A response generated from local mock data, canned question matching, or a disabled AI provider must be marked as degraded/mock/fallback and cannot satisfy production commit-ready validation.
- Dev/test-only mocks must be gated by explicit environment/config and reported in completion output.

## 2. FE -> BE dialogue request

Path:

```http
POST /api/v1/sessions/{sessionId}/dialogue
Content-Type: application/json
```

Request:

```json
{
  "suspectId": "char_hanseoyeon",
  "message": "22시 이후 어디에 있었나요?",
  "questionId": null
}
```

Rules:
- `message` is natural-language input.
- `questionId` is optional and should only be used if FE intentionally pins a known question.
- BE classifies `dialogueMode`: `small_talk`, `unmatched`, `case_question`, `evidence_question`, etc.
- `small_talk` and `unmatched` do not consume remaining questions and do not create implicit fact notes.

## 3. BE -> AI dialogue request target

Path:

```http
POST /internal/v1/dialogue/respond
Content-Type: application/json
```

Target payload:

```json
{
  "requestId": "req_...",
  "correlationId": "corr_...",
  "caseId": "case_001",
  "sessionId": "sess_...",
  "currentActId": "alibi_collection",
  "currentObjective": "22시 전후 각 인물의 위치 진술을 확보한다.",
  "dialogueMode": "case_question",
  "intent": "location_time",
  "consumedQuestion": true,
  "suspect": {
    "id": "char_hanseoyeon",
    "name": "한서연",
    "role": "조카",
    "publicProfile": "상속 문제로 피해자와 갈등이 있었다.",
    "publicPersona": "차갑고 계산적이며 질문을 통제하려 한다.",
    "speechStyle": {
      "register": "formal",
      "baseTone": "cold_defensive",
      "sentenceLength": "medium",
      "vocabulary": ["오해", "정확히", "불쾌하군요"],
      "low": { "tone": "controlled", "hesitation": "low" },
      "medium": { "tone": "defensive", "hesitation": "medium" },
      "high": { "tone": "sharp", "hesitation": "high" },
      "critical": { "tone": "fractured", "hesitation": "very_high" }
    },
    "publicTimeline": [
      {
        "timelineId": "ctl_hanseoyeon_2200_claim_room",
        "time": "22:00",
        "title": "방에 있었다는 주장",
        "summary": "한서연은 22시 이후 계속 방에 있었다고 말한다.",
        "sourceType": "statement",
        "sourceId": "st_hanseoyeon_room_2200",
        "relatedEvidenceIds": ["ev_study_entry_log"],
        "relatedStatementIds": ["st_hanseoyeon_room_2200"],
        "relatedContradictionIds": ["con_room_claim_vs_entry_log"]
      }
    ],
    "pressure": 0,
    "pressureState": "normal",
    "tensionLevel": "low",
    "tensionScore": 0,
    "emotionalState": "neutral",
    "expression": "confident_lying"
  },
  "message": "22시 이후 어디에 있었나요?",
  "question": {
    "id": "q_hanseoyeon_alibi",
    "text": "22시 이후 어디에 있었나요?"
  },
  "allowedStatement": {
    "id": "st_hanseoyeon_room_2200",
    "text": "저는 22시 이후 계속 제 방에 있었습니다.",
    "sourceRefs": {
      "statementIds": ["st_hanseoyeon_room_2200"],
      "timelineIds": ["ctl_hanseoyeon_2200_claim_room"],
      "evidenceIds": []
    }
  },
  "storyline": {
    "publicPremise": "폭풍우 치던 밤 저택 2층 서재에서 강도준이 쓰러진 채 발견된다.",
    "currentActId": "alibi_collection",
    "currentObjective": "22시 전후 각 인물의 위치 진술을 확보한다.",
    "visibleTimeline": [
      {
        "timelineId": "tl_global_2202_study_entry",
        "time": "22:02",
        "title": "서재 출입 기록",
        "description": "22:02에 서재 문이 열린 기록이 있다.",
        "sourceType": "evidence",
        "sourceId": "ev_study_entry_log"
      }
    ]
  },
  "characterTimeline": {
    "suspectId": "char_hanseoyeon",
    "publicPersona": "차갑고 계산적인 태도",
    "events": [
      {
        "timelineId": "ctl_hanseoyeon_2200_claim_room",
        "time": "22:00",
        "claimedLocation": "한서연의 방",
        "claimedAction": "혼자 쉬고 있었다고 주장",
        "relatedEvidenceIds": ["ev_study_entry_log"],
        "relatedStatementIds": ["st_hanseoyeon_room_2200"],
        "emotionalState": "neutral",
        "public": true
      }
    ]
  },
  "visibleFacts": {
    "evidence": [
      { "id": "ev_study_entry_log", "name": "서재 출입 기록", "description": "22:02에 서재 문이 열렸다." }
    ],
    "statements": [
      { "id": "st_hanseoyeon_room_2200", "suspectId": "char_hanseoyeon", "text": "저는 22시 이후 계속 제 방에 있었습니다." }
    ],
    "records": [],
    "relations": []
  },
  "characterKnowledgePack": {
    "packId": "ckp_case_001_char_hanseoyeon_sess_123_evt_000007",
    "caseId": "case_001",
    "sessionId": "sess_...",
    "suspectId": "char_hanseoyeon",
    "visibility": "public",
    "publicPersona": "차갑고 계산적이며 질문을 통제하려 한다.",
    "speechStyle": {},
    "personaVariants": {
      "baseline": {
        "variantId": "pv_hanseoyeon_baseline",
        "tensionLevel": "low",
        "pressureState": "normal",
        "emotionalState": "neutral",
        "tone": "controlled",
        "evasiveness": 0.35,
        "hesitation": "low",
        "allowedTone": ["formal", "precise", "guarded"],
        "forbiddenTone": ["confessional", "solution reveal"],
        "visibility": "public"
      },
      "pressed": {
        "variantId": "pv_hanseoyeon_pressed",
        "tensionLevel": "high",
        "pressureState": "pressed",
        "emotionalState": "shocked",
        "tone": "sharp_defensive",
        "evasiveness": 0.7,
        "hesitation": "high",
        "allowedTone": ["defensive", "curt"],
        "forbiddenTone": ["private motive reveal", "full confession"],
        "visibility": "public"
      }
    },
    "activePersonaOverlay": {
      "variantId": "pv_hanseoyeon_pressed",
      "selectionReason": "tensionLevel=high pressureState=pressed emotionalState=shocked recentDialoguePressure=0.8",
      "tensionLevel": "high",
      "pressureState": "pressed",
      "emotionalState": "shocked",
      "tensionScore": 58,
      "contradictionPressure": {
        "contradictionIds": ["con_room_claim_vs_entry_log"],
        "newlyDiscovered": false,
        "alreadyDiscovered": true
      },
      "recentDialoguePressure": 0.8,
      "tone": "sharp_defensive",
      "evasiveness": 0.7,
      "hesitation": "high",
      "allowedTone": ["defensive", "curt"],
      "forbiddenTone": ["private motive reveal", "full confession"]
    },
    "visibleTimeline": [],
    "alibiSnippets": [],
    "evidenceSnippets": [],
    "relationshipSnippets": [],
    "recentDialogue": [],
    "forbiddenRefs": ["secret", "solution", "privateTimeline", "privateEvents", "privateMotive", "privateRefs", "culprit", "culpritId", "isCulprit", "finalDiscovery", "finalVerdict", "actualAction", "actualLocation", "secretNote"]
  },
  "dialogueHistorySummary": "탐정은 사건 개요를 확인했고 아직 핵심 모순은 제기하지 않았다.",
  "visualState": {
    "suspectId": "char_hanseoyeon",
    "backgroundId": "mansion_study_night",
    "characterImageState": "neutral",
    "emotionalState": "neutral",
    "expression": "confident_lying",
    "tensionLevel": "low"
  },
  "style": { "tone": "neutral", "maxLength": 220 },
  "revealAllowed": false,
  "allowedEventPolicy": {
    "allowedTypes": ["NOTE_FACT_ADDED", "NOTE_CONTRADICTION_CANDIDATE_ADDED", "BOOKMARK_SUGGESTED", "VISUAL_REACTION_SUGGESTED"],
    "relatedEvidenceIds": ["ev_study_entry_log"],
    "relatedTimelineEventIds": ["ctl_hanseoyeon_2200_claim_room"],
    "relatedStatementIds": ["st_hanseoyeon_room_2200"],
    "relatedQuestionIds": ["q_hanseoyeon_alibi"],
    "relatedContradictionIds": ["con_room_claim_vs_entry_log"]
  }
}
```

Mandatory BE -> AI rules:
- Include `requestId` and preferably `correlationId` in every request.
- `revealAllowed` must be `false` for interrogation dialogue.
- Do not send private truth fields: `secret`, `solution`, `privateTimeline`, private timeline events, `privateEvents`, `privateMotive`, `privateRefs`, `culprit`, `culpritId`, `isCulprit`, `finalDiscovery`, `finalVerdict`, `actualAction`, `actualLocation`, `secretNote`.
- `suspect.tensionLevel` is a label string: `low|medium|high|critical`.
- Numeric intensity is `suspect.pressure` and optional `suspect.tensionScore`.
- `allowedStatement` is the factual anchor for answer text.
- `publicTimeline` and `visibleFacts` may ground style/context only unless referenced in `allowedStatement.sourceRefs` or `allowedEventPolicy`.
- `characterKnowledgePack` must be public-only and must include `personaVariants` plus `activePersonaOverlay` for the selected suspect.
- `activePersonaOverlay` is voice/style input only. It must not grant hidden facts or mutate tension.

Current implementation delta:
- BE currently sends `currentActId`, `dialogueMode`, `intent`, `consumedQuestion`, `suspect`, `message`, `question`, `allowedStatement`, `visibleFacts`, `dialogueHistorySummary`, `style`, `revealAllowed`.
- BE does not yet send target `currentObjective`, `storyline`, `characterTimeline`, `characterKnowledgePack`, `visualState`, or `allowedEventPolicy` in dialogue AI payload.
- AI schema currently types `suspect.tensionLevel` as int; update to label string and use `pressure`/`tensionScore` for numeric intensity.

## 4. AI -> BE dialogue response target

Response:

```json
{
  "statementId": "st_hanseoyeon_room_2200",
  "requestId": "req_...",
  "correlationId": "corr_...",
  "answer": "정확히 말하면, 저는 22시 이후 계속 제 방에 있었습니다. 그 이상은 기억에 없습니다.",
  "text": "정확히 말하면, 저는 22시 이후 계속 제 방에 있었습니다. 그 이상은 기억에 없습니다.",
  "dialogueMode": "case_question",
  "intent": "location_time",
  "provider": "openai",
  "model": "gpt-...",
  "fallbackUsed": false,
  "safety": {
    "leaksSolution": false,
    "violatesCaseFacts": false,
    "blockedTerms": [],
    "fallbackUsed": false,
    "provider": "openai",
    "model": "gpt-...",
    "repaired": false,
    "blockedReason": null
  },
  "degraded": false,
  "visualState": {
    "suspectId": "char_hanseoyeon",
    "backgroundId": "mansion_study_night",
    "characterImageState": "neutral",
    "emotionalState": "neutral",
    "expression": "confident_lying",
    "tensionLevel": "low"
  },
  "proposedEvents": [
    {
      "type": "NOTE_FACT_ADDED",
      "payload": {
        "sourceType": "statement",
        "sourceId": "st_hanseoyeon_room_2200",
        "statementIds": ["st_hanseoyeon_room_2200"],
        "timelineIds": ["ctl_hanseoyeon_2200_claim_room"]
      }
    }
  ]
}
```

Rules:
- `answer` and `text` should be equivalent during migration; BE may read either.
- `proposedEvents[]` use stable IDs and are never assumed applied.
- AI must not propose `NOTE_FACT_ADDED` for `small_talk`/`unmatched` unless `allowedEventPolicy.allowedTypes` explicitly permits and payload has stable visible refs.
- AI must not include private truth or solution in text, proposed events, safety metadata, provider logs, or visual state.
- If provider generation fails, AI returns either a non-2xx error with request metadata or an explicit degraded response. It must not return fabricated character testimony as if provider generation succeeded.

## 5. BE EventProcessor validation contract

Event types BE may accept from AI after validation:
- `NOTE_FACT_ADDED`
- `NOTE_CONTRADICTION_CANDIDATE_ADDED`
- `BOOKMARK_SUGGESTED`
- `VISUAL_REACTION_SUGGESTED`
- public unlock/candidate event types for relationship, evidence, evidence detail, timeline, and notebook entries when explicitly allowed by `allowedEventPolicy`

Event types AI must not propose:
- `TENSION_CHANGED`
- final contradiction verdict/discovery events
- direct session state mutation events
- private truth reveal events when `revealAllowed=false`

Canonical `NOTE_FACT_ADDED` proposal:

```json
{
  "type": "NOTE_FACT_ADDED",
  "payload": {
    "sourceType": "statement",
    "sourceId": "st_hanseoyeon_room_2200",
    "statementIds": ["st_hanseoyeon_room_2200"],
    "evidenceIds": [],
    "timelineIds": ["ctl_hanseoyeon_2200_claim_room"]
  }
}
```

Canonical `NOTE_CONTRADICTION_CANDIDATE_ADDED` proposal:

```json
{
  "type": "NOTE_CONTRADICTION_CANDIDATE_ADDED",
  "payload": {
    "candidateId": "cand_con_room_claim_vs_entry_log_st_hanseoyeon_room_2200_ev_study_entry_log",
    "contradictionId": "con_room_claim_vs_entry_log",
    "suspectId": "char_hanseoyeon",
    "statementIds": ["st_hanseoyeon_room_2200"],
    "evidenceIds": ["ev_study_entry_log"],
    "timelineIds": ["ctl_hanseoyeon_2200_claim_room", "tl_global_2202_study_entry"],
    "confidence": 0.85,
    "reasonCode": "same_time_location_conflict",
    "displayText": "한서연의 방 알리바이와 22:02 서재 출입 기록이 충돌할 수 있습니다.",
    "submitEligible": true
  }
}
```

BE application rules:
- BE regenerates or sanitizes public note text from visible sources.
- BE rejects events whose source IDs are absent or not visible/unlocked.
- BE rejects unsupported event types or malformed payloads.
- BE dedupes proposed events by stable IDs before persistence.
- BE may append system-owned `VISUAL_STATE_CHANGED` after processing.
- BE may append system-owned `TENSION_CHANGED` only through BE `TensionPolicy` after a new validated evidence + testimony/alibi contradiction is discovered.

TensionPolicy rules:
- Generic dialogue, small talk, unmatched dialogue, fact notes, relationship unlocks, evidence unlocks, evidence-detail unlocks, timeline unlocks, notebook/bookmark updates, and contradiction candidate creation do not raise tension by themselves.
- Duplicate proposed events, SSE replay, repeated questions, and repeated contradiction submissions for an already discovered contradiction must not increment pressure again.
- AI degraded/failure responses must not create `TENSION_CHANGED`, unlock progress, contradiction discovery, or objective advancement.
- `TENSION_CHANGED` payloads are BE-owned and should include `suspectId`, `contradictionId` when applicable, `pressure`, `previousPressure`, `pressureDelta`, `pressureState`, `tensionLevel`, and optional `tensionScore`.

Current implementation delta:
- BE currently validates `NOTE_FACT_ADDED` with `sourceType/sourceId` and safe text generation.
- BE currently validates contradiction candidate primarily by `contradictionId` and unlocked required IDs.
- AI current proposal uses `sourceStatementId`/`relatedEvidenceIds`, which is not canonical and may be rejected by BE. Migrate to `contradictionId`, `statementIds`, `evidenceIds`, and `timelineIds`.

## 6. BE -> FE session/dialogue response

`POST /dialogue` response is the visible session payload plus dialogue metadata.

Target shape excerpt:

```json
{
  "sessionId": "sess_...",
  "caseId": "case_001",
  "phase": "investigation",
  "remainingQuestions": 11,
  "selectedSuspectId": "char_hanseoyeon",
  "opening": {},
  "storyline": {
    "publicPremise": "...",
    "acts": [],
    "timeline": [],
    "cluePaths": []
  },
  "visibleTimeline": [],
  "currentObjective": "22시 전후 각 인물의 위치 진술을 확보한다.",
  "currentActId": "alibi_collection",
  "suspects": [
    {
      "characterId": "char_hanseoyeon",
      "name": "한서연",
      "role": "조카",
      "publicProfile": "상속 문제로 피해자와 갈등이 있었다.",
      "publicPersona": "차갑고 계산적인 태도",
      "speechStyle": {},
      "publicTimeline": [],
      "pressure": 35,
      "pressureState": "pressed",
      "tensionLevel": "medium",
      "tensionScore": 35,
      "emotionalState": "defensive",
      "expression": "defensive"
    }
  ],
  "dialogueLog": [],
  "notes": [],
  "notebook": {
    "caseFile": {},
    "evidence": [],
    "records": [],
    "statements": [],
    "statementsBySuspect": {},
    "questionsBySuspect": {},
    "relations": [],
    "relationMap": {},
    "contradictions": [],
    "bookmarks": [],
    "notes": []
  },
  "caseFile": {},
  "relationMap": {
    "centerCharacterId": "victim_kangdojun",
    "nodes": [],
    "edges": []
  },
  "evidence": [],
  "records": [],
  "relations": [],
  "statements": [],
  "questions": [],
  "contradictions": [],
  "unlockedQuestionIds": [],
  "newlyUnlockedIds": [],
  "discoveredContradictionIds": [],
  "pressureBySuspect": { "char_hanseoyeon": 35 },
  "lastEventId": "evt_000012",
  "visualState": {
    "suspectId": "char_hanseoyeon",
    "backgroundId": "mansion_study_night",
    "characterImageState": "defensive",
    "emotionalState": "defensive",
    "expression": "defensive",
    "tensionLevel": "medium"
  },
  "dialogueResult": {
    "messageId": "dlg_...",
    "requestId": "req_...",
    "correlationId": "corr_...",
    "suspectId": "char_hanseoyeon",
    "dialogueMode": "case_question",
    "intent": "location_time",
    "matchedQuestionId": "q_hanseoyeon_alibi",
    "matchedIntentId": "q_hanseoyeon_alibi",
    "repeated": false,
    "askCount": 1,
    "remainingQuestions": 11,
    "previousRemainingQuestions": 12,
    "remainingQuestionsDelta": -1,
    "unlockedIds": ["st_hanseoyeon_room_2200"],
    "consumedQuestion": true,
    "fallbackUsed": false,
    "degraded": false,
    "provider": "openai",
    "model": "gpt-...",
    "safety": { "leaksSolution": false, "violatesCaseFacts": false },
    "emotionalState": "defensive",
    "tensionLevel": "medium",
    "proposedEventsCount": 1,
    "appliedEventsCount": 1,
    "lastEventId": "evt_000012"
  },
  "proposedEventsCount": 1,
  "appliedEventsCount": 1,
  "proposedEventsApplied": ["evt_000011"]
}
```

Public hidden-field ban applies to the whole response.

Current implementation delta:
- BE currently returns most fields above, including `dialogueResult`, proposed/applied counts, `visualState`, `lastEventId`, and suspects with `publicProfile`, `speechStyle`, `publicTimeline`, `pressureState`, `tensionLevel`, `emotionalState`.
- BE does not currently include `model` in `dialogueResult`.
- FE type normalizer does not preserve `speechStyle`/`publicTimeline` on `Suspect` view yet.
- BE latest smoke reports `caseFile`, `relationMap`, `notebook`, public `contradictions`, and notes CRUD/SSE are available through the 8080 API proxy. FE must bind UI panels to these public read models rather than local placeholders.

## 7. SSE event contract

Path:

```http
GET /api/v1/sessions/{sessionId}/events
Accept: text/event-stream
Last-Event-ID: evt_000012
```

SSE event data shape:

```json
{
  "id": "evt_000013",
  "sessionId": "sess_...",
  "caseId": "case_001",
  "type": "NOTE_CONTRADICTION_CANDIDATE_ADDED",
  "payload": {
    "noteId": "note_...",
    "contradictionId": "con_room_claim_vs_entry_log",
    "statementIds": ["st_hanseoyeon_room_2200"],
    "evidenceIds": ["ev_study_entry_log"],
    "text": "모순 후보: 방 알리바이와 서재 출입 기록"
  },
  "createdAt": "2026-06-01T...Z"
}
```

Required event behavior:
- `id` must be monotonically ordered per session or otherwise usable as `Last-Event-ID`.
- Event payloads should include `correlationId`/`requestId` when caused by a request.
- FE applies only public payloads.
- `VISUAL_STATE_CHANGED` payload should match canonical `visualState` shape.
- `TENSION_CHANGED` payload should include `suspectId`, `pressure`, `pressureState`, `tensionLevel`, and optionally `tensionScore`.
- `TENSION_CHANGED` must be emitted only by BE after TensionPolicy accepts a new contradiction discovery. AI-sourced `TENSION_CHANGED` is invalid and must be rejected.
- `NOTE_CREATED`, `NOTE_UPDATED`, and `NOTE_DELETED` payloads should include public note IDs and changed fields or enough data for FE to refresh notes from BE.
- Relationship/notebook/evidence/contradiction updates should either emit typed public events or require FE to refresh `GET /sessions/{sessionId}` after `lastEventId` advances.

## 8. Visual update precedence

When HTTP response and SSE both include visual/tension metadata:
1. Newer BE session state/event wins.
2. FE may apply HTTP `visualState` immediately.
3. FE reconciles with SSE replay using `lastEventId`.
4. Local/mock fallback state is marked `source=local` and must not be mistaken for validated game state.

## 9. Runtime diagnostics visibility

Developer-visible in MVP debug strip/panels:
- `correlationId`
- `requestId`
- `source` API vs LOCAL
- `provider`
- `model`
- `fallbackUsed`
- `safety` summary
- `dialogueMode`/`intent`
- `matchedQuestionId`
- `proposedEventsCount`/`appliedEventsCount`
- `lastEventId`
- `remainingQuestions`, previous, delta
- `tensionLevel`, `emotionalState`, `expression`

Player-visible in polished build:
- current objective/current act
- visible evidence/notes/timeline
- suspect emotion/tension via visual presentation, not raw provider/safety diagnostics
- contradiction candidate display text after BE validation

Never player-visible:
- private truth fields
- raw prompt content
- API keys/provider secrets
- `secret`, `solution`, `privateTimeline`, private timeline entries, `privateEvents`, `privateRefs`, `culprit`, `culpritId`, `isCulprit`, `finalDiscovery`, `finalVerdict`, `actualAction`, `actualLocation`, `secretNote`

## 10. Production fallback and degraded semantics

Status semantics:
- `fallbackUsed=false`, `degraded=false`: normal production path. BE called AI, AI called configured provider or approved deterministic production adapter, BE validated events.
- `fallbackUsed=true`, `degraded=false`: a safe repair or provider fallback occurred, but the response is still explicitly tagged and must include provider/fallback metadata.
- `degraded=true`: service could not provide normal character dialogue. FE should show retry/degraded state and must not treat the answer as canonical testimony.
- `source=LOCAL` or `source=MOCK`: dev/test preview only. This blocks production commit-ready dogfood.

Failure rules:
- AI timeout/provider error must not decrement question count unless BE intentionally records a failed attempt with explicit semantics.
- AI failure must not create `NOTE_FACT_ADDED`, contradiction candidates, evidence unlocks, `TENSION_CHANGED`, objective advancement, or any progress event.
- BE may emit a public diagnostic event for observability, but it must not leak provider secrets or private story truth.
- FE must surface API/SSE/provider fallback state in diagnostics and must not hide it behind normal-looking dialogue.

Config gates:
- Mock provider mode must be enabled only by explicit env/config and must be visible in health or diagnostics.
- Production-like Docker validation must use real service-to-service URLs and fail readiness or report degraded state if AI is unavailable.
- Completion reports must state provider mode, fallback path, and whether any local/mock path was active.

## 11. Observability and health contract

Required health/readiness:
- FE runtime reachable through configured port/proxy.
- BE health endpoint reachable directly and through FE/proxy path when used.
- AI health/readiness endpoint reachable directly from host and from BE container/network when Docker is used.
- Health should distinguish service process availability from provider/dependency readiness when feasible.

Required structured log fields:
- `correlationId`, `requestId`, `sessionId`, `caseId`, `suspectId`
- route/operation name and duration
- `dialogueMode`, `intent`, `matchedQuestionId`
- `provider`, `model`, `fallbackUsed`, `degraded`, `blockedReason`
- `proposedEventsCount`, `appliedEventsCount`, rejected event reasons
- `lastEventId`, `Last-Event-ID`, replay count for SSE

SSE diagnostics:
- FE/BE validation should prove replay from `Last-Event-ID` works.
- Unknown or stale `Last-Event-ID` behavior must be deterministic and logged.
- Event IDs must let FE reconcile HTTP response state against newer event stream state.

## 12. FE investigation UI contract

FE must render the following from BE public payloads:
- `caseFile` panel: opening, rules, current objective/act, visible timeline, and public premise.
- Evidence panel/detail drawer: evidence name/type/description/foundAt/timeWindow/reliability/unlock state/source refs/asset.
- Relationship map: nodes/edges from `relationMap`, with relationship labels, public descriptions, lock state, and stable refs.
- Notebook/notes: note list from BE plus create form using `POST /notes`; update/delete only if BE supports them.
- Statements/testimony: public `statements` and `statementsBySuspect` for selecting contradiction targets.
- Contradictions: candidate/discovered detail from public `contradictions`, not only raw IDs.

FE must not treat buttons as complete if they do not open a populated BE-backed panel or drawer.

## 13. Notes service contract

Create note request:

```json
{
  "text": "한서연의 방 알리바이와 서재 출입 기록을 비교한다.",
  "linkedEvidenceIds": ["ev_study_entry_log"],
  "linkedStatementIds": ["st_hanseoyeon_room_2200"],
  "linkedRecordIds": [],
  "linkedContradictionIds": ["con_room_claim_vs_entry_log"],
  "linkedSuspectIds": ["char_hanseoyeon"]
}
```

Acceptance:
- BE persists the note under the session.
- Response and later `GET /sessions/{sessionId}` include the note.
- SSE emits `NOTE_CREATED` or FE has a documented refresh path.
- FE visibly reflects BE-returned note data and marks failure/fallback instead of silently saving local-only notes.

## 14. Contradiction selection contract

Direct contradiction submission is player-selected:

```json
{
  "suspectId": "char_hanseoyeon",
  "statementIds": ["st_hanseoyeon_room_2200"],
  "evidenceIds": ["ev_study_entry_log"]
}
```

Rules:
- FE must require selecting at least one public statement/testimony and one public evidence item.
- BE validates IDs, unlock state, and matching contradiction.
- BE returns deterministic contradiction result and updated public read models.
- AI-proposed contradiction candidates can guide the player, but cannot auto-submit final truth.

## 15. Dialogue bubble contract

Canonical turn item, whether explicit or derived during migration:

```json
{
  "messageId": "dlg_...",
  "speakerType": "player",
  "speakerName": "탐정",
  "suspectId": "char_hanseoyeon",
  "text": "22시 이후 어디에 있었나요?",
  "order": 3,
  "createdAt": "2026-06-01T00:00:00Z"
}
```

Rules:
- FE main dialogue area renders each player and suspect turn as separate chronological bubbles.
- Suspect turns show speaker name and may show portrait/expression from current or turn-level visual state.
- A compact debug/history log may exist, but the main UX must not be an answer-only card with duplicated lower text.

## 16. Visual asset delivery contract

FE asset mapping must cover canonical expressions:

```text
neutral,wary,defensive,angry,anxious,shocked,breakdown,confident_lying,sad,focused
```

Rules:
- Every suspect has a neutral fallback and at least the expressions referenced by their `tensionProfile`.
- Missing asset paths, broken image requests, and placeholder-looking SVGs are validation blockers.
- ImageGen/provider-generated noir comic PNG/WebP assets are acceptable and preferred for character portraits.

## 17. Acceptance checks for contract implementation

BE -> AI:
- `revealAllowed=false` for dialogue.
- `suspect.tensionLevel` is label string and `pressure` numeric is present.
- no hidden/private fields in request body or logs.
- `allowedEventPolicy` present before AI can propose fact/contradiction events.
- `requestId`/`correlationId` appear in request/response/logs.
- AI provider failure yields explicit degraded/failure semantics and no fabricated progress.
- `allowedEventPolicy` never delegates `TENSION_CHANGED` to AI.

AI -> BE:
- answer remains inside allowed public facts.
- implementation uses first-class models from `Docs/story-agent-contract.md`: `CharacterAgentInput`, `DraftCharacterReply`, `LightRuleCheckInput`, `CheckedCharacterReply`, `GameMasterAgentInput`, `GameMasterProposal`.
- proposed events use stable IDs and canonical payload fields.
- small talk/unmatched returns no fact proposed events.
- safety metadata indicates leak/fact violations clearly.
- provider/model/fallback/degraded/safety metadata is populated.
- AI never proposes `TENSION_CHANGED` or final contradiction verdict/discovery state.

BE -> FE:
- session payload contains `opening`, `storyline`, `visibleTimeline`, `currentObjective`, `currentActId`.
- suspects contain public timeline/style/tension/emotion fields.
- dialogue response contains provider/fallback/safety/proposed/applied counts/lastEventId.
- public payload leak scan passes.
- health/proxy/SSE replay diagnostics pass in production-like Docker path.
- `TENSION_CHANGED` is BE-owned, idempotent, monotonic, and only follows new validated evidence + testimony/alibi contradiction discovery.

FE:
- diagnostics show API-vs-LOCAL and event counts.
- visual state changes portrait/background selectors.
- SSE replay/update is reconciled with HTTP state.
- per-turn dialogue bubbles render player and suspect messages with speaker identity.
- case/evidence/notes/relation/contradiction panels use BE read models and notes APIs.
- contradiction flow requires selected statement/testimony plus evidence.
- character/evidence assets are coherent noir comic assets with no broken URLs.
