# Story Data Contract

Owner: DOCS
Scope: target case JSON and scenario/story data model. BE implements this as runtime source of truth; AI and FE consume public projections only.

## 1. File paths and ownership

Canonical runtime case file today:
- `BE/data/cases/case_001.json`

Target runtime schema owners:
- BE domain models: `BE/app/domain/models.py`
- BE public filtering: `BE/app/domain/case_engine.py`
- DOCS canonical contract: this file and `Docs/story-architecture.md`

Scenario notes/prose in `Docs/Senario/*.md` are design source material, not runtime API truth until migrated into BE case JSON.

CaseWiki/Obsidian knowledge graph source:
- `Docs/story-knowledge-wiki-contract.md` defines the next high-priority authoring model for fact pages, evidence pages, character pages, relationship edges, timeline layers, and case detail chains.
- BE may compile wiki pages into runtime case JSON or a deterministic knowledge graph index.
- AI and FE still consume public projections only.

## 2. Stable ID prefixes

Required stable references:

| Object | Prefix | Example |
| --- | --- | --- |
| Case | `case_` | `case_001` |
| Scene | `scene_` | `scene_001` |
| Character/suspect | `char_` | `char_hanseoyeon` |
| Evidence | `ev_` | `ev_study_entry_log` |
| Record | `rec_` | `rec_will_revision_notice` |
| Relationship | `rel_` | `rel_hanseoyeon_victim_inheritance` |
| Statement | `st_` | `st_hanseoyeon_room_2200` |
| Question | `q_` | `q_hanseoyeon_alibi` |
| Global timeline | `tl_` | `tl_global_2202_study_entry` |
| Character timeline | `ctl_` | `ctl_hanseoyeon_2202_study` |
| Contradiction | `con_` | `con_room_claim_vs_entry_log` |
| Clue path | `path_` | `path_alibi_break` |
| Visual asset semantic | `vis_` | `vis_hanseoyeon_high_shocked` |
| Note | `note_` | `note_player_entry_log_question` |
| Contradiction candidate | `cand_` | `cand_con_room_claim_vs_entry_log` |
| Fact | `fact_` | `fact_hanseoyeon_claim_room_2200` |
| Rumor | `rumor_` | `rumor_will_revision` |
| Chain | `chain_` | `chain_hanseoyeon_opportunity` |

Every public/proposed/applied event must reference these IDs rather than free-text truth.

## 3. Top-level target shape

```json
{
  "caseId": "case_001",
  "sceneId": "scene_001",
  "title": "진실은, 서로의 말 속에 있다",
  "summary": "폭풍우 치던 밤 저택 서재에서 피해자가 발견된다.",
  "victimId": "victim_kangdojun",
  "victimName": "강도준",
  "incidentTime": "22:00~22:10",
  "incidentLocation": "2층 서재",
  "questionLimit": 12,
  "opening": {},
  "storyline": {},
  "suspects": [],
  "characterTimelines": [],
  "evidence": [],
  "records": [],
  "relations": [],
  "statements": [],
  "questions": [],
  "contradictions": [],
  "visualProfiles": [],
  "solution": {}
}
```

Public API rule:
- `solution` is runtime-private.
- `suspects[].secret`, `suspects[].isCulprit`, `characterTimelines[].privateEvents`, private motives, and hidden timeline entries must not appear in public payloads.

## 4. `opening`

```json
{
  "hook": "폭풍우가 저택을 고립시킨 밤, 강도준이 서재에서 쓰러진 채 발견됐다.",
  "objective": "네 명의 진술과 객관 증거를 대조해 동시에 성립할 수 없는 말을 찾으세요.",
  "rules": [
    "자연어로 용의자에게 질문하세요.",
    "진술과 증거를 조합해 모순을 제기하세요.",
    "공개되지 않은 진실은 추측이 아니라 단서 해금으로 확인해야 합니다."
  ],
  "victoryCondition": "핵심 모순을 확보한 뒤 범인, 동기, 수단, 근거를 제출한다."
}
```

Public: yes.
Hidden fields: none.

## 5. `storyline`

```json
{
  "publicPremise": "폭풍우 치던 밤 저택 2층 서재에서 강도준이 쓰러진 채 발견된다. 외부 침입 흔적은 없다.",
  "acts": [
    {
      "actId": "alibi_collection",
      "title": "알리바이 수집",
      "objective": "22시 전후 각 인물의 위치 진술을 확보한다.",
      "entryCondition": "session_start",
      "focusSuspectIds": ["char_hanseoyeon", "char_parkmingyu"],
      "recommendedQuestionIds": ["q_hanseoyeon_alibi", "q_parkmingyu_alibi"],
      "requiredClueIds": ["st_hanseoyeon_room_2200", "st_parkmingyu_guestroom_2200"],
      "playerHint": "같은 시간대에 누가 어디 있었다고 주장하는지 먼저 모으세요.",
      "completionCondition": "핵심 알리바이 진술 2개 이상 확보"
    }
  ],
  "timeline": [
    {
      "timelineId": "tl_global_2202_study_entry",
      "time": "22:02",
      "title": "서재 출입 기록",
      "description": "22:02에 서재 문이 열린 기록이 있다.",
      "sourceType": "evidence",
      "sourceId": "ev_study_entry_log",
      "unlockCondition": null,
      "hidden": false
    },
    {
      "timelineId": "tl_global_2206_scene_manipulation",
      "time": "22:06",
      "title": "숨겨진 현장 조작",
      "description": "정전 중 현장 조작이 있었다.",
      "sourceType": "inference",
      "sourceId": "solution_hidden_scene_manipulation",
      "unlockCondition": "final_reveal_only",
      "hidden": true
    }
  ],
  "cluePaths": [
    {
      "pathId": "path_alibi_break",
      "title": "방 알리바이 검증",
      "objective": "한서연의 22:00 위치 진술을 객관 기록과 비교한다.",
      "steps": [
        { "order": 1, "type": "statement", "id": "st_hanseoyeon_room_2200", "prompt": "한서연은 22:00에 어디 있었다고 말하는가?" },
        { "order": 2, "type": "evidence", "id": "ev_study_entry_log", "prompt": "22:02 서재 출입 기록과 비교하라." }
      ],
      "resolvesContradictionId": "con_room_claim_vs_entry_log",
      "unlocks": ["q_hanseoyeon_after_pressure", "ev_torn_will"],
      "secretNote": "비공개: 범인의 첫 거짓말을 드러낸다. public payload에서 제거"
    }
  ],
  "currentObjectiveRules": [
    {
      "priority": 100,
      "when": { "missingContradictionId": "con_room_claim_vs_entry_log" },
      "objective": "한서연의 방 알리바이와 서재 출입 기록을 비교하세요.",
      "actId": "first_break"
    }
  ]
}
```

Public projection rules:
- `publicPremise`, `acts`, visible `timeline`, public clue paths are public.
- `timeline[].hidden=true` entries are removed.
- `cluePaths[].secretNote` is removed.
- `currentObjectiveRules` may remain BE-private and be projected as `currentObjective/currentActId` only.

## 6. `suspects[]` persona/speech/tension

Target suspect shape:

```json
{
  "characterId": "char_hanseoyeon",
  "name": "한서연",
  "role": "조카",
  "publicProfile": "상속 문제로 피해자와 갈등이 있었다.",
  "persona": {
    "publicPersona": "차갑고 계산적인 태도를 유지하지만 상속 이야기에 예민하게 반응한다.",
    "publicMask": "침착한 상속인",
    "privateMotive": "유언장 변경으로 상속분을 잃을까 두려워했다. public/revealAllowed=false 금지",
    "secret": "22:02에 서재에 들어갔고 정전 중 현장을 조작했다. public 금지"
  },
  "speechStyle": {
    "register": "formal",
    "baseTone": "cold_defensive",
    "sentenceLength": "medium",
    "vocabulary": ["정확히", "오해", "불쾌하군요"],
    "avoid": ["과장된 감정 표현", "정답 직접 암시"],
    "low": { "tone": "controlled", "hesitation": "low", "sample": "그 시간엔 제 방에 있었습니다." },
    "medium": { "tone": "defensive", "hesitation": "medium", "sample": "그 기록만으로 절 의심하시는 건가요?" },
    "high": { "tone": "sharp", "hesitation": "high", "sample": "몰아붙이지 마세요. 전 그렇게 말한 적 없습니다." },
    "critical": { "tone": "fractured", "hesitation": "very_high", "sample": "잠깐... 그건 설명할 수 있습니다." }
  },
  "tensionProfile": {
    "initialPressure": 0,
    "thresholds": [
      { "level": "low", "min": 0, "max": 29, "emotionalState": "neutral", "expression": "confident_lying" },
      { "level": "medium", "min": 30, "max": 44, "emotionalState": "defensive", "expression": "defensive" },
      { "level": "high", "min": 45, "max": 69, "emotionalState": "shocked", "expression": "shocked" },
      { "level": "critical", "min": 70, "max": 100, "emotionalState": "breakdown", "expression": "breakdown" }
    ],
    "triggers": [
      { "onContradictionId": "con_room_claim_vs_entry_log", "pressureDelta": 35, "expression": "shocked" }
    ]
  },
  "motiveCandidate": true,
  "isCulprit": true
}
```

Public projection:
- Include `characterId`, `name`, `role`, `publicProfile`, `persona.publicPersona`, public `speechStyle`, current `pressure`, `pressureState`, `tensionLevel`, `tensionScore`, `emotionalState`, `expression`, and public timeline.
- Remove `persona.privateMotive`, `persona.secret`, top-level `secret`, and `isCulprit`.

Tension data ownership:
- `tensionProfile.thresholds[]` and `tensionProfile.triggers[]` are case-data configuration for BE-owned TensionPolicy.
- AI may read public current tension/emotion/expression to shape voice, but AI does not apply pressure changes and does not emit `TENSION_CHANGED`.
- Unlocking relationship/evidence/evidence detail/timeline/notebook entries does not itself imply pressure change.
- Pressure changes require BE validation of a new evidence + testimony/alibi contradiction discovery.

Persona injection contract:
- `personaVariants` and `activePersonaOverlay` are the canonical public voice model for the 3-Agent pipeline.
- BE compiles them into `CharacterKnowledgePack` from case JSON and/or CaseWiki/Obsidian public frontmatter.
- Variants should cover at least `baseline`, `calm`, `defensive`, `pressed`, `nervous`, `broken`, and `angry` when the character supports those states.
- See `Docs/story-agent-contract.md` for the Pydantic/JSON schemas and frontmatter examples.

## 7. Expression taxonomy and visual asset semantics

Canonical expression enum for MVP:

```text
neutral
wary
defensive
angry
anxious
shocked
breakdown
confident_lying
sad
focused
```

Canonical tension labels:

```text
low
medium
high
critical
```

Canonical emotional state enum:

```text
neutral
wary
defensive
angry
anxious
shocked
breakdown
confident
confident_lying
```

Asset naming recommendation:

```text
assets/characters/{characterId}/{expression}.png
assets/backgrounds/{backgroundId}.png
```

Example:

```json
{
  "visualProfiles": [
    {
      "characterId": "char_hanseoyeon",
      "portraits": [
        { "expression": "confident_lying", "assetId": "vis_hanseoyeon_confident_lying", "assetPath": "assets/characters/char_hanseoyeon/confident_lying.png" },
        { "expression": "shocked", "assetId": "vis_hanseoyeon_shocked", "assetPath": "assets/characters/char_hanseoyeon/shocked.png" },
        { "expression": "breakdown", "assetId": "vis_hanseoyeon_breakdown", "assetPath": "assets/characters/char_hanseoyeon/breakdown.png" }
      ]
    }
  ]
}
```

FE may accept unknown expression strings during migration, but canonical case data and BE visualState should use this enum.

Asset quality rule:
- Canonical expression entries must resolve to generated or production-quality noir comic/cartoon portraits, with a documented neutral fallback per suspect.
- Placeholder SVG silhouettes, broken image URLs, and unstyled generic avatars do not satisfy the visual contract.
- Evidence assets should depict the object or record clearly enough to support evidence inspection and cross-examination.

## 8. `characterTimelines[]`

Canonical first-class character timeline shape:

```json
{
  "timelineId": "ct_char_hanseoyeon",
  "suspectId": "char_hanseoyeon",
  "publicPersona": "차갑고 계산적인 태도를 유지하지만 상속 이야기에 예민하다.",
  "privateMotive": "상속분 축소를 막기 위해 피해자와 갈등했다. public 금지",
  "publicEvents": [
    {
      "timelineId": "ctl_hanseoyeon_2200_claim_room",
      "time": "22:00",
      "location": "한서연의 방",
      "claimedLocation": "한서연의 방",
      "claimedAction": "혼자 쉬고 있었다고 주장",
      "summary": "한서연은 22시 이후 계속 방에 있었다고 말한다.",
      "sourceType": "statement",
      "sourceId": "st_hanseoyeon_room_2200",
      "relatedEvidenceIds": ["ev_study_entry_log"],
      "relatedStatementIds": ["st_hanseoyeon_room_2200"],
      "relatedQuestionIds": ["q_hanseoyeon_alibi"],
      "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
      "unlockCondition": "st_hanseoyeon_room_2200",
      "revealCondition": "statement_unlocked",
      "visibility": "public",
      "isClaim": true,
      "isLieKnownToSystem": true,
      "displayHint": "방 알리바이와 객관 기록을 비교하세요."
    }
  ],
  "privateEvents": [
    {
      "timelineId": "ctl_hanseoyeon_2202_actual_study",
      "time": "22:02",
      "actualLocation": "2층 서재",
      "actualAction": "서재에 들어가 피해자와 대면했다.",
      "privateNote": "핵심 범행 동선. public/revealAllowed=false 금지",
      "sourceType": "solution",
      "sourceId": "solution_hanseoyeon_actual_route",
      "relatedEvidenceIds": ["ev_study_entry_log"],
      "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
      "visibility": "private",
      "revealCondition": "ending_reveal"
    }
  ],
  "contradictionSeeds": [
    {
      "contradictionId": "con_room_claim_vs_entry_log",
      "statementIds": ["st_hanseoyeon_room_2200"],
      "evidenceIds": ["ev_study_entry_log"],
      "timelineIds": ["ctl_hanseoyeon_2200_claim_room", "tl_global_2202_study_entry"],
      "publicPrompt": "방에 있었다는 진술과 서재 출입 기록이 동시에 성립하는가?",
      "privateNote": "첫 압박 모순"
    }
  ]
}
```

Public/private rules:
- `publicEvents[]` can be projected to `suspects[].publicTimeline` after unlock/reveal conditions pass.
- `privateEvents[]` never appear in public payloads or AI prompt when `revealAllowed=false`.
- `privateMotive`, `actualAction`, `actualLocation`, `privateNote` are hidden unless an ending/reveal endpoint explicitly uses `revealAllowed=true`.

## 9. Public timeline projection

Canonical `suspects[].publicTimeline[]` item:

```json
{
  "timelineId": "ctl_hanseoyeon_2200_claim_room",
  "time": "22:00",
  "title": "방에 있었다는 주장",
  "summary": "한서연은 22시 이후 계속 방에 있었다고 말한다.",
  "location": "한서연의 방",
  "claimedLocation": "한서연의 방",
  "claimedAction": "혼자 쉬고 있었다고 주장",
  "sourceType": "statement",
  "sourceId": "st_hanseoyeon_room_2200",
  "relatedEvidenceIds": ["ev_study_entry_log"],
  "relatedStatementIds": ["st_hanseoyeon_room_2200"],
  "relatedQuestionIds": ["q_hanseoyeon_alibi"],
  "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
  "revealCondition": "statement_unlocked",
  "isClaim": true,
  "displayHint": "객관 기록과 비교 가능"
}
```

Do not include:
- `actualAction`
- `actualLocation` when it is private truth
- `privateMotive`
- `privateNote`
- `isCulprit`
- `secret`

## 10. Example: Han Seo-yeon

```json
{
  "characterId": "char_hanseoyeon",
  "name": "한서연",
  "role": "조카",
  "publicProfile": "상속 문제로 피해자와 갈등이 있었다.",
  "persona": {
    "publicPersona": "차갑고 계산적이며 질문을 통제하려 한다.",
    "publicMask": "침착한 상속인",
    "privateMotive": "유언장 변경으로 상속분이 줄어드는 것을 막으려 했다.",
    "secret": "22:02 서재 출입 및 정전 중 현장 조작"
  },
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
  "tensionProfile": {
    "initialPressure": 0,
    "thresholds": [
      { "level": "low", "min": 0, "max": 29, "emotionalState": "neutral", "expression": "confident_lying" },
      { "level": "medium", "min": 30, "max": 44, "emotionalState": "defensive", "expression": "defensive" },
      { "level": "high", "min": 45, "max": 69, "emotionalState": "shocked", "expression": "shocked" },
      { "level": "critical", "min": 70, "max": 100, "emotionalState": "breakdown", "expression": "breakdown" }
    ]
  },
  "motiveCandidate": true,
  "isCulprit": true
}
```

Character timeline excerpt:

```json
{
  "timelineId": "ct_char_hanseoyeon",
  "suspectId": "char_hanseoyeon",
  "publicEvents": [
    {
      "timelineId": "ctl_hanseoyeon_2200_claim_room",
      "time": "22:00",
      "title": "방에 있었다는 주장",
      "summary": "한서연은 22시 이후 계속 방에 있었다고 말한다.",
      "claimedLocation": "한서연의 방",
      "claimedAction": "혼자 쉬고 있었다고 주장",
      "sourceType": "statement",
      "sourceId": "st_hanseoyeon_room_2200",
      "relatedStatementIds": ["st_hanseoyeon_room_2200"],
      "relatedEvidenceIds": ["ev_study_entry_log"],
      "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
      "unlockCondition": "st_hanseoyeon_room_2200",
      "visibility": "public"
    }
  ],
  "privateEvents": [
    {
      "timelineId": "ctl_hanseoyeon_2202_actual_study",
      "time": "22:02",
      "actualLocation": "2층 서재",
      "actualAction": "서재에 들어가 피해자와 대면했다.",
      "visibility": "private",
      "revealCondition": "ending_reveal"
    }
  ]
}
```

## 11. Example: Park Min-gyu non-culprit

```json
{
  "characterId": "char_parkmingyu",
  "name": "박민규",
  "role": "주치의",
  "publicProfile": "피해자의 건강과 약 복용 기록을 관리하던 주치의다.",
  "persona": {
    "publicPersona": "전문성을 앞세워 차분히 말하지만 의료 과실 의심에는 예민하다.",
    "publicMask": "침착한 전문가",
    "privateMotive": "의료 과실 의혹을 피하고 싶어 한다. 범행 동기는 아님.",
    "secret": "약 처방 오류를 의심받을까 두려워 일부 설명을 축소했다. 범인은 아님."
  },
  "speechStyle": {
    "register": "formal",
    "baseTone": "clinical_calm",
    "sentenceLength": "long",
    "vocabulary": ["의학적으로", "복용량", "기록상"],
    "low": { "tone": "calm", "hesitation": "low" },
    "medium": { "tone": "technical_defensive", "hesitation": "low" },
    "high": { "tone": "irritated_authoritative", "hesitation": "medium" },
    "critical": { "tone": "strained", "hesitation": "high" }
  },
  "tensionProfile": {
    "initialPressure": 0,
    "thresholds": [
      { "level": "low", "min": 0, "max": 29, "emotionalState": "neutral", "expression": "focused" },
      { "level": "medium", "min": 30, "max": 44, "emotionalState": "defensive", "expression": "defensive" },
      { "level": "high", "min": 45, "max": 69, "emotionalState": "angry", "expression": "angry" },
      { "level": "critical", "min": 70, "max": 100, "emotionalState": "anxious", "expression": "anxious" }
    ]
  },
  "motiveCandidate": false,
  "isCulprit": false
}
```

Character timeline excerpt:

```json
{
  "timelineId": "ct_char_parkmingyu",
  "suspectId": "char_parkmingyu",
  "publicEvents": [
    {
      "timelineId": "ctl_parkmingyu_2130_medicine",
      "time": "21:30",
      "title": "약 복용 확인",
      "summary": "박민규는 피해자의 21:30 복용 기록에는 치명적 이상이 없었다고 말한다.",
      "claimedLocation": "진료 기록 보관실",
      "claimedAction": "복용 기록을 확인했다",
      "sourceType": "statement",
      "sourceId": "st_parkmingyu_medicine_2130",
      "relatedEvidenceIds": ["ev_medicine_box"],
      "relatedStatementIds": ["st_parkmingyu_medicine_2130"],
      "relatedQuestionIds": ["q_parkmingyu_medicine"],
      "relatedContradictionIds": [],
      "unlockCondition": "q_parkmingyu_medicine",
      "visibility": "public"
    },
    {
      "timelineId": "ctl_parkmingyu_2200_guestroom",
      "time": "22:00",
      "title": "손님방 알리바이",
      "summary": "박민규는 22시 무렵 손님방에서 의료 기록을 정리했다고 주장한다.",
      "claimedLocation": "손님방",
      "claimedAction": "의료 기록 정리",
      "sourceType": "statement",
      "sourceId": "st_parkmingyu_guestroom_2200",
      "relatedStatementIds": ["st_parkmingyu_guestroom_2200"],
      "visibility": "public"
    }
  ],
  "privateEvents": [
    {
      "timelineId": "ctl_parkmingyu_private_malpractice_fear",
      "time": "21:30~22:00",
      "actualLocation": "손님방",
      "actualAction": "의료 기록을 다시 확인하며 과실 의심을 우려했다.",
      "visibility": "private",
      "revealCondition": "medical_red_herring_resolved"
    }
  ]
}
```

## 12. `allowedEventPolicy`

Target BE -> AI policy shape:

```json
{
  "allowedTypes": [
    "NOTE_FACT_ADDED",
    "NOTE_CONTRADICTION_CANDIDATE_ADDED",
    "BOOKMARK_SUGGESTED",
    "VISUAL_REACTION_SUGGESTED"
  ],
  "relatedEvidenceIds": ["ev_study_entry_log"],
  "relatedTimelineEventIds": ["ctl_hanseoyeon_2200_claim_room", "tl_global_2202_study_entry"],
  "relatedStatementIds": ["st_hanseoyeon_room_2200"],
  "relatedQuestionIds": ["q_hanseoyeon_alibi"],
  "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
  "noteFactAllowed": true,
  "contradictionCandidateAllowed": true,
  "visualReactionAllowed": true
}
```

Policy rule:
- `small_talk` and `unmatched` should send `allowedTypes: []` unless BE intentionally allows a non-fact visual reaction.
- AI proposed events outside this policy are rejected by BE.

## 13. Contradiction candidate event shape

Canonical AI -> BE proposed event:

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

BE validation:
- `contradictionId` must exist.
- Required statement/evidence IDs must be unlocked or otherwise visible.
- `candidateId` may be provided by AI but BE may replace with deterministic ID.
- `displayText` is sanitized or regenerated by BE before public notes/SSE.

Current BE accepts `contradictionId` for canonical validation. Migration should add stable candidate fields without removing BE validation authority.

## 14. Investigation read models

BE owns public investigation read models. FE consumes these from session/dialogue responses, SSE, and notes endpoints; FE must not invent local-only canonical truth.

### `caseFile`

```json
{
  "caseId": "case_001",
  "title": "진실은, 서로의 말 속에 있다",
  "opening": {},
  "publicPremise": "폭풍우 치던 밤 저택 2층 서재에서 강도준이 쓰러진 채 발견된다.",
  "currentActId": "alibi_collection",
  "currentObjective": "22시 전후 각 인물의 위치 진술을 확보한다.",
  "visibleTimeline": []
}
```

### `relationMap`

```json
{
  "centerCharacterId": "victim_kangdojun",
  "nodes": [
    {
      "id": "char_hanseoyeon",
      "type": "suspect",
      "name": "한서연",
      "role": "조카",
      "publicProfile": "상속 문제로 피해자와 갈등이 있었다.",
      "locked": false,
      "sourceRefs": ["rel_hanseoyeon_victim_inheritance"]
    }
  ],
  "edges": [
    {
      "id": "rel_hanseoyeon_victim_inheritance",
      "from": "char_hanseoyeon",
      "to": "victim_kangdojun",
      "label": "상속 갈등",
      "description": "유언장 변경 문제로 갈등이 있었다.",
      "locked": false,
      "evidenceIds": ["rec_will_revision_notice"],
      "statementIds": []
    }
  ]
}
```

### `notebook`

```json
{
  "caseFile": {},
  "evidence": [],
  "records": [],
  "statements": [],
  "statementsBySuspect": {
    "char_hanseoyeon": []
  },
  "questionsBySuspect": {
    "char_hanseoyeon": []
  },
  "relations": [],
  "relationMap": {},
  "contradictions": [],
  "bookmarks": [],
  "notes": []
}
```

### `notes[]`

```json
{
  "noteId": "note_player_entry_log_question",
  "type": "player",
  "text": "한서연의 방 알리바이와 서재 출입 기록을 대조해야 한다.",
  "linkedEvidenceIds": ["ev_study_entry_log"],
  "linkedStatementIds": ["st_hanseoyeon_room_2200"],
  "linkedRecordIds": [],
  "linkedContradictionIds": ["con_room_claim_vs_entry_log"],
  "linkedSuspectIds": ["char_hanseoyeon"],
  "createdAt": "2026-06-01T00:00:00Z",
  "updatedAt": "2026-06-01T00:00:00Z"
}
```

Notes mutation scope:
- MVP must support create and persisted read from BE.
- If update/delete are supported, they must emit public SSE and keep `GET /sessions/{sessionId}` consistent.
- If update/delete are not supported in a milestone, the limitation must be documented in completion reports and FE must not show misleading controls.

### Evidence detail

Evidence objects must carry enough public detail for a drawer/panel:
- `evidenceId`, `name`, `type`, `description`
- `foundAt`, `timeWindow`, `reliability`
- `initiallyVisible`, `unlockCondition`, public lock state
- `sourceRefs` or explicit linked statement/record/timeline/contradiction IDs where public
- `assetId`/`assetPath` when available

### Contradiction detail

Public contradiction read model:

```json
{
  "contradictionId": "con_room_claim_vs_entry_log",
  "title": "방 알리바이와 서재 출입 기록",
  "relatedCharacterId": "char_hanseoyeon",
  "requiredStatementIds": ["st_hanseoyeon_room_2200"],
  "requiredEvidenceIds": ["ev_study_entry_log"],
  "timelineIds": ["ctl_hanseoyeon_2200_claim_room", "tl_global_2202_study_entry"],
  "severity": "core",
  "status": "candidate",
  "displayText": "방에 있었다는 진술과 22:02 서재 출입 기록이 충돌할 수 있습니다.",
  "unlocked": true,
  "discovered": false
}
```

FE contradiction submission must send player-selected statement/testimony IDs plus evidence IDs. `discoveredContradictionIds` alone is insufficient for FE detail rendering.

## 15. BE case data vs DOCS story source vs AI prompt-only contract

BE case data:
- runtime truth source loaded by `CaseRepository`
- all public/private scenario facts required for validation and projections
- stable IDs and unlock/reveal conditions
- persona/speech/tension/visual semantic configuration after migration

DOCS story source:
- canonical design and migration contract
- may include explanatory prose, diagrams, and rationale
- not consumed at runtime unless migrated into BE case JSON

AI prompt-only contract:
- public-only projection from BE for one request
- may contain compact summaries and style hints derived from BE case data
- must not contain private truth with `revealAllowed=false`
- cannot become source of truth or create new facts outside stable IDs and `allowedStatement`

## 16. Migration plan

1. Add Pydantic models in `BE/app/domain/models.py`: `Persona`, `SpeechStyle`, `TensionProfile`, `CharacterTimeline`, `CharacterTimelineEvent`, `VisualProfile`.
2. Add target JSON fields to `BE/data/cases/case_001.json`.
3. Replace `public_speech_style(characterId)` hardcoding with case-data lookup and fallback adapter.
4. Replace derived public timeline source-ID matching with `characterTimelines[].publicEvents` projection.
5. Update BE -> AI payload to include `storyline`, selected `characterTimeline`, `visibleFacts`, and `allowedEventPolicy`.
6. Update AI schema `Suspect.tensionLevel` to label string and add optional `pressure`/`tensionScore` numeric fields.
7. Update FE type model to include `speechStyle`, `publicTimeline`, `tensionScore`, canonical `expression`, and event candidate fields.
8. Keep BE public `caseFile`, `relationMap`, `notebook`, evidence detail, notes, and contradiction detail read models stable for FE panels.
9. Replace FE local-only investigation controls with BE-backed panels and SSE/session refresh.
10. Replace placeholder character/evidence assets with generated noir comic assets mapped to canonical expressions and evidence IDs.
