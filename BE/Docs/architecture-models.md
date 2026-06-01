# Backend architecture and model map

This document is the BE-local map for future backend agents. It documents the current runtime shape, public/hidden boundaries, and migration gaps against the canonical DOCS story contracts. Canonical story architecture is owned by DOCS; this file references the canonical target docs rather than inventing story schema.

Canonical references:

- `../../Docs/story-architecture.md`
- `../../Docs/story-data-contract.md`
- `../../Docs/service-contract-dialogue-story.md`
- `../../Docs/story-validation-gates.md`
- `../../Docs/Senario/schema.md`

## Scope

Backend is the authoritative service for:

- case JSON loading and Pydantic validation
- session state and unlock persistence
- deterministic question, contradiction, and accusation verdicts
- free-text dialogue classification and AI request context assembly
- validating GameMaster `proposedEvents`
- publishing validated session updates through SSE
- building FE-safe public payloads

AI may draft dialogue and propose events, but BE validates and applies state changes.

## Case JSON to public session payload

```mermaid
flowchart LR
    A["data/cases/*.json"] --> B["CaseRepository._load_all()"]
    B --> C["Case.model_validate(data)"]
    C --> D["Pydantic Case domain model"]
    D --> E["initial_session_state(case, sessionId)"]
    E --> F["SessionState"]
    D --> G["visible_session_payload(session, case)"]
    F --> G
    G --> H["GET /api/v1/sessions/{id}"]
    G --> I["POST /dialogue merged response"]

    subgraph PublicFilters["Public filtering rules"]
      P1["timeline: hidden=false and source visible"]
      P2["evidence/records/relations/statements/questions: unlocked IDs only"]
      P3["cluePaths: secretNote removed"]
      P4["suspects: publicProfile only; no secret/isCulprit"]
      P5["solution: never included"]
    end
    G -. applies .-> PublicFilters
```

Key code paths:

- `app/infra/case_repository.py`: loads JSON and validates `Case`.
- `app/domain/models.py`: Pydantic domain models for case and session state.
- `app/domain/case_engine.py`: initializes sessions, applies unlocks, builds public payloads.
- `app/api/routes_sessions.py`: merges `lastEventId` and `visualState` into session responses.

## Dialogue and event flow

```mermaid
sequenceDiagram
    participant FE as FE
    participant Route as routes_sessions.py
    participant DS as DialogueService
    participant RE as RuleEngine
    participant AI as AIClient
    participant EP as EventProcessor
    participant ER as EventRepository
    participant SSE as /sessions/{id}/events

    FE->>Route: POST /sessions/{id}/dialogue {suspectId,message,questionId?}
    Route->>DS: submit(sessionId, suspectId, message, questionId)
    DS->>DS: classify dialogueMode and match visible question/evidence context
    alt consumed case question
        DS->>RE: answer_question(session, case, questionId)
        RE-->>DS: answer, unlock IDs, repeated/askCount
    else small_talk / unmatched / unconsumed evidence_question
        DS->>DS: no decrement, no question consumption
    end
    DS->>AI: /internal/v1/dialogue/respond with public persona/timeline/tension/visibleFacts
    AI-->>DS: answer, provider, fallbackUsed, safety, proposedEvents[]
    DS->>EP: process_dialogue_events(..., proposedEvents, allow_implicit_note)
    EP->>EP: validate proposedEvents against visible IDs/rules
    EP->>ER: append_many(validated EventEntry[])
    DS-->>Route: answer + dialogueResult + session/case
    Route-->>FE: visible_session_payload + answer + diagnostics + visualState + lastEventId
    FE->>SSE: GET /sessions/{id}/events Last-Event-ID?
    SSE->>ER: replay events after cursor
    SSE-->>FE: validated event-stream
```

Dialogue response diagnostic fields exposed to FE:

- `answer`
- `dialogueResult.messageId`
- `dialogueResult.suspectId`
- `dialogueResult.dialogueMode` / `dialogueResult.intent`
- `dialogueResult.matchedQuestionId` nullable for `small_talk`, `unmatched`, or unconsumed evidence context
- `dialogueResult.consumedQuestion`
- `dialogueResult.previousRemainingQuestions`
- `dialogueResult.remainingQuestions`
- `dialogueResult.remainingQuestionsDelta`
- `dialogueResult.repeated`, `askCount`, `unlockedIds`
- `dialogueResult.provider`, `fallbackUsed`, `safety`
- `dialogueResult.proposedEventsCount`, `appliedEventsCount`
- `dialogueResult.emotionalState`, `tensionLevel`
- top-level `provider`, `fallbackUsed`, `safety`, `proposedEventsCount`, `appliedEventsCount`
- `proposedEventsApplied` event IDs
- `visualState`
- merged session fields, including `lastEventId`

## Event validation flow

```mermaid
flowchart TD
    A["AI/GameMaster proposedEvents[]"] --> B["EventProcessor._validate_proposed_event"]
    B --> C{"supported type and dict payload?"}
    C -- no --> R["reject + warning log"]
    C -- yes --> D{"event type"}

    D -- NOTE_FACT_ADDED --> NF["Require sourceType + sourceId/targetId"]
    NF --> NF2{"source visible to session?"}
    NF2 -- no --> R
    NF2 -- yes --> NF3["Generate safe note text from BE case/session source"]
    NF3 --> NF4["append NoteEntry + EventEntry"]

    D -- NOTE_CONTRADICTION_CANDIDATE_ADDED --> NC["Require contradictionId"]
    NC --> NC2{"contradiction exists?"}
    NC2 -- no --> R
    NC2 -- yes --> NC3{"requiredStatementIds unlocked?"}
    NC3 -- no --> R
    NC3 -- yes --> NC4{"requiredEvidenceIds unlocked?"}
    NC4 -- no --> R
    NC4 -- yes --> NC5["append linked contradiction note + EventEntry"]

    D -- EVIDENCE_UNLOCKED --> EU["Allow only session.newlyUnlockedIds"]
    D -- TIMELINE_EVENT_REVEALED --> TL["Allow only visible_timeline sourceId"]
    D -- TENSION_CHANGED --> TN["Rebuild safe pressure payload from session"]
    D -- VISUAL_STATE_CHANGED --> VS["Rebuild safe visualState from session"]
    D -- BOOKMARK_SUGGESTED --> BM["Require visible target"]
    D -- VISUAL_REACTION_SUGGESTED --> VR["Rebuild safe visualState"]

    EU --> OK["EventEntry"]
    TL --> OK
    TN --> OK
    VS --> OK
    BM --> OK
    VR --> OK
    NF4 --> OK
    NC5 --> OK
    OK --> E["EventRepository.append_many"]
    E --> S["SSE replay / stream"]
```

Important behavior:

- `small_talk` and `unmatched` call `process_dialogue_events(..., allow_implicit_note=False)` and do not create `NOTE_FACT_ADDED` unless a validated explicit proposed event supplies a visible source reference.
- For consumed case/evidence questions, BE may add an implicit fact note if no validated `NOTE_FACT_ADDED` was proposed.
- AI text is not trusted as authoritative note content for proposed fact notes. BE derives note text from visible source IDs.
- Contradiction candidate notes require a known `contradictionId` whose required statement/evidence IDs are currently visible/unlocked.

## Data model relationships

```mermaid
erDiagram
    Case ||--o| Opening : has
    Case ||--o| Storyline : has
    Storyline ||--o{ StoryAct : contains
    Storyline ||--o{ TimelineEvent : contains
    Storyline ||--o{ CluePath : contains
    CluePath ||--o{ CluePathStep : contains
    Storyline ||--o{ ObjectiveRule : contains

    Case ||--o{ Character : suspects
    Case ||--o{ CharacterTimeline : target_characterTimelines
    Case ||--o{ VisualProfile : target_visualProfiles
    Case ||--o{ Evidence : evidence
    Case ||--o{ Record : records
    Case ||--o{ Relationship : relations
    Case ||--o{ Statement : statements
    Case ||--o{ Question : questions
    Case ||--o{ Contradiction : contradictions
    Case ||--|| Solution : hidden_solution

    Character ||--o{ Statement : characterId
    Character ||--o{ Question : characterId
    Character ||--o{ Relationship : characterId
    Character ||--o{ Contradiction : relatedCharacterId
    Character ||--o{ CharacterTimeline : suspectId
    Character ||--o{ VisualProfile : suspectId
    Question ||--o{ Statement : unlocksStatementIds
    Question ||--o{ Evidence : unlocksEvidenceIds
    Question ||--o{ Record : unlocksRecordIds
    Question ||--o{ Relationship : unlocksRelationIds
    Contradiction ||--o{ Statement : requiredStatementIds
    Contradiction ||--o{ Evidence : requiredEvidenceIds

    Case ||--o{ SessionState : creates
    SessionState ||--o{ DialogueEntry : dialogueLog
    SessionState ||--o{ NoteEntry : notes
    SessionState ||--o{ BookmarkEntry : bookmarks
    SessionState ||--o{ EventEntry : event_stream
    SessionState }o--o{ Evidence : unlockedEvidenceIds
    SessionState }o--o{ Record : unlockedRecordIds
    SessionState }o--o{ Relationship : unlockedRelationIds
    SessionState }o--o{ Statement : unlockedStatementIds
    SessionState }o--o{ Question : unlockedQuestionIds
    SessionState }o--o{ Contradiction : discoveredContradictionIds
```

## Public vs hidden/private field boundary

### Hidden/private in case data or domain models

These fields must not appear in FE public payloads or AI public dialogue context unless a future DOCS-owned contract explicitly allows a reveal path:

- `Character.secret`
- `Character.isCulprit`
- `Case.solution`
- `Solution.culpritId`, `motive`, `method`, `required*`, `endings`
- `TimelineEvent.hidden`
- hidden global timeline entries before they become public by an explicit rule
- target `characterTimelines[].privateEvents`
- target private character timeline fields such as private `actualAction`/`actualLocation` truth
- target `persona.privateMotive`, `persona.secret`
- `CluePath.secretNote`
- any private character timeline/persona fields added later

### Exposed to FE via session payload

Current safe public fields include:

- session: `sessionId`, `caseId`, `phase`, `remainingQuestions`, `selectedSuspectId`, `lastEventId`, `visualState`
- story: `opening`, public `storyline.publicPremise`, acts, public clue paths without `secretNote`, `visibleTimeline`
- suspects: `characterId`, `name`, `role`, `publicProfile`, target `publicPersona`, `motiveCandidate`, `pressure`, `pressureState`, `tensionLevel`, target `tensionScore`, `emotionalState`, target `expression`, `speechStyle`, `publicTimeline`
- session content: `dialogueLog`, `notes`, `bookmarks`
- visible/unlocked collections: `evidence`, `records`, `relations`, `statements`, `questions`
- state IDs: `unlockedQuestionIds`, `askedQuestionCounts`, `newlyUnlockedIds`, `discoveredContradictionIds`, `pressureBySuspect`, `pressureStates`
- accusation summary after accusation: submitted motive/method may be preserved in public response; deterministic verdict remains based on IDs

### Exposed to AI dialogue endpoint

`DialogueService` sends only BE-curated context:

- `caseId`, `sessionId`, `currentActId`; target also includes `requestId` and `currentObjective`
- `dialogueMode` / `intent`
- `consumedQuestion`
- selected suspect public fields: `id`, `name`, `role`, `publicProfile`, target `publicPersona`, `speechStyle`, `publicTimeline`, `pressure`, `pressureState`, `tensionLevel` label, target `tensionScore`, `emotionalState`, target `expression`
- player `message`
- matched `question` if any
- `allowedStatement` for matched context or neutral fallback context; target shape includes `sourceRefs`
- `visibleFacts`: currently visible statement/evidence/record IDs, discovered contradiction IDs, current objective/act, visible timeline
- target `storyline`, `characterTimeline`, `visualState`, and `allowedEventPolicy`
- `dialogueHistorySummary`
- `style` hint and `revealAllowed=false`

AI must not receive `secret`, `isCulprit`, full `solution`, private timeline entries, or hidden timeline items.

## Canonical decisions and BE migration plan

DOCS accepted the canonical story/data/dialogue contract in `../../Docs/story-data-contract.md` and `../../Docs/service-contract-dialogue-story.md`. BE-local implementation status:

1. `suspect.tensionLevel` is canonically a label string: `low | medium | high | critical`.
   - Current BE already sends label strings to AI and FE.
   - Numeric intensity is `suspect.pressure`; target may also expose `suspect.tensionScore` as a numeric alias/normalized score.
2. `characterTimelines[]` is first-class target case data.
   - Current BE does not have `Case.characterTimelines` yet.
   - Current BE derives `suspects[].publicTimeline` from visible global `storyline.timeline` entries whose source IDs match the character's visible statements/questions. This is a temporary adapter, not the accepted target shape.
   - Migration: add Pydantic models for `CharacterTimeline` with public/private event split, migrate `case_001.json`, and build `suspects[].publicTimeline` from `characterTimelines[].publicEvents` filtered by stable visible IDs.
3. `speechStyle` and `tensionProfile` belong in BE case data after migration.
   - Current BE uses `public_speech_style(characterId)` hardcoded mapping as a temporary adapter.
   - Migration: add `Character.persona`, `Character.speechStyle`, and `Character.tensionProfile`; remove hardcoded speech adapter once case data is migrated.
4. `allowedStatement` remains the factual anchor.
   - `publicTimeline` and `visibleFacts` may shape tone/context.
   - They may ground factual dialogue text only when referenced by `allowedStatement.sourceRefs` or `allowedEventPolicy` stable IDs.
   - Migration: enrich `_allowed_statement_for_question`/evidence context with `sourceRefs`, and include an `allowedEventPolicy` in BE -> AI payload.
5. Target BE -> AI payload additions still needed.
   - Add `requestId`, `currentObjective`, `storyline`, `characterTimeline`, `visualState`, and `allowedEventPolicy`.
   - Keep `revealAllowed=false` for interrogation dialogue.
6. Target visual fields still needed.
   - Canonical expression enum: `neutral`, `wary`, `defensive`, `angry`, `anxious`, `shocked`, `breakdown`, `confident_lying`, `sad`, `focused`.
   - Current BE exposes `characterImageState`/`emotionalState` and `tensionLevel`, but not a separate `expression` everywhere.
   - Migration: add `expression` to `visualState`, suspects, and relevant SSE payloads; use `tensionProfile` thresholds after case data migration.
7. Canonical contradiction candidate proposed event shape is richer than current BE validation.
   - Target payload fields: `candidateId`, `contradictionId`, `suspectId`, `statementIds`, `evidenceIds`, `timelineIds`, `confidence`, `reasonCode`, `displayText`, `submitEligible`.
   - Current BE validates primarily by `contradictionId` plus unlocked required statement/evidence IDs and regenerates public note text.
   - Migration: accept the richer payload shape, validate all supplied stable IDs, continue regenerating public text, and include safe canonical fields in SSE payload.

## Current implementation deltas against canonical docs

The runtime supports FE/AI with safe public fields, but these gaps remain relative to DOCS canonical contracts:

1. `Case.characterTimelines` missing from Pydantic model and case JSON.
2. `Character.persona`, `Character.speechStyle`, and `Character.tensionProfile` missing from Pydantic model and case JSON.
3. `suspects[].publicTimeline` is derived from global timeline source matching instead of `characterTimelines[].publicEvents`.
4. `allowedStatement.sourceRefs` is not consistently populated.
5. BE -> AI payload does not yet include target `requestId`, `currentObjective`, `storyline`, `characterTimeline`, `visualState`, or `allowedEventPolicy`.
6. `visualState.expression`, `suspects[].expression`, and `suspects[].tensionScore` are target fields but not consistently exposed by current runtime.
7. `TENSION_CHANGED` SSE payload should include `tensionLevel` and optionally `tensionScore`; current payload includes `pressure` and `pressureState`.
8. `NOTE_CONTRADICTION_CANDIDATE_ADDED` validation should migrate to the canonical candidate payload while preserving BE-side sanitization/regeneration.

These are now accepted migration items rather than open story-contract questions. Future runtime work should implement them against the canonical DOCS files above.

## File map

```mermaid
flowchart TB
    Routes["app/api/routes_sessions.py"] --> Dialogue["app/application/dialogue_service.py"]
    Routes --> Commands["app/application/session_commands.py"]
    Dialogue --> Rule["app/domain/rule_engine.py"]
    Dialogue --> AI["app/infra/ai_client.py"]
    Dialogue --> EventProcessor["app/domain/event_processor.py"]
    EventProcessor --> Events["app/domain/event_types.py"]
    Routes --> SSE["app/infra/sse_transport.py"]
    Routes --> EventRepo["app/infra/event_repository.py"]
    Commands --> CaseEngine["app/domain/case_engine.py"]
    CaseEngine --> Models["app/domain/models.py"]
    Repo["app/infra/case_repository.py"] --> Models
    SessionRepo["app/infra/session_repository.py"] --> Models
```

## Maintenance rules

- Update this document when changing public session payload, dialogue response contract, event types, or domain models.
- If a change alters story schema or public/private reveal semantics, send `CROSS-FEEDBACK` to DOCS and copy `orchest:1.1` before assuming a target shape.
- Runtime changes require normal BE tests and Docker refresh. Docs-only changes do not require Docker refresh.
