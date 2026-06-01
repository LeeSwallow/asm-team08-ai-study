# Storyline Structure Foundation Plan

> 최종 시나리오와 이벤트 기반 아키텍처 상세는 `Docs/final-scenario-and-event-architecture.md`를 기준으로 한다.

> 목적: 현재 단일 flat case JSON을 PRD의 핵심 재미인 “대화 속 진술 간 모순 발견”이 드러나는 사건 구조로 재정렬한다. 시나리오와 각 캐릭터의 개인 타임라인을 분리해 만들고, 플레이어가 자연어 대화로 드러난 정보와 모순 축을 이해할 수 있게 만든다.

## 핵심 원칙

1. 사건의 진실(truth)과 플레이어 공개 정보(public storyline)를 분리한다.
2. 플레이어에게는 act/objective/timeline/clue path를 보여주되 culprit/solution/secret은 공개 API에서 절대 노출하지 않는다.
3. 게임 진행은 아래 루프로 고정한다.
   - 도입 → 알리바이 수집 → 첫 모순 제기 → 압박/해금 → 동기 확정 → 최종 지목 → 엔딩
4. 시나리오 작성 시 전체 사건 타임라인과 각 캐릭터별 개인 타임라인을 함께 작성한다. 개인 타임라인에는 실제 행적, 공개 알리바이, 거짓말/누락, 감정 변화, 증거 연결을 명시한다.
5. AI는 storyline을 새로 만들지 않는다. BE가 제공한 공개 storyline context 안에서 CharacterAgent가 답변을 생성하고, LightRuleCheck가 이상 대화를 검증하며, GameMasterAgent는 상태 변경 대신 `proposedEvents[]`를 생성한다.
6. GameMasterAgent가 제안한 사건노트/증거/타임라인/긴장도 변경은 Backend Event Processor가 검증한 뒤 SSE 또는 WebSocket으로 UI에 비동기 발행한다.
7. Background 이미지와 캐릭터 이미지는 현재 장소, 사건 단계, 긴장도/감정 상태에 따라 바뀔 수 있어야 한다.
8. Docker compose로 FE/BE/AI가 모두 빌드/실행 가능해야 한다.

## Target Case Schema Additions

### case.opening
- hook: string
- objective: string
- rules: string[]
- victoryCondition: string

### case.storyline.publicPremise
플레이어에게 보여도 되는 사건 전제.

### case.storyline.scenario
사건 작성을 위한 전체 시나리오. 공개/비공개를 분리한다.
- synopsis: string — 전체 사건 요약
- truthSummary: string — 실제 진실. 공개 API 노출 금지
- publicSummary: string — 플레이어에게 공개 가능한 요약
- centralMystery: string
- culpritTheory: string — 범인/동기/수법. 공개 API 노출 금지
- emotionalTone: string
- backgroundPlan: [{ stateId, locationId, actId, tensionRange, assetId, description }]

### case.storyline.characterTimelines[]
각 캐릭터의 개인 타임라인. “실제 행적”과 “주장한 알리바이”를 분리해야 한다.
- suspectId: string
- publicPersona: string — 플레이어에게 공개 가능한 성격/관계 요약
- privateMotive?: string — 비공개 동기. 공개 API 노출 금지
- events: [{
    time,
    actualLocation,
    claimedLocation,
    actualAction,
    claimedAction,
    witnessedBy: string[],
    relatedEvidenceIds: string[],
    relatedStatementIds: string[],
    emotionalState: neutral | tense | surprised | angry | broken,
    tensionDelta: number,
    isLie: boolean,
    public: boolean,
    unlockCondition?: string
  }]
- contradictionSeeds: [{ statementId, conflictsWithIds, note }]

### case.visualAssets
긴장도와 감정 상태에 따른 배경/캐릭터 이미지 매핑.
- backgrounds: [{ id, locationId, actId, tensionMin, tensionMax, assetPath }]
- characterImages: [{ suspectId, state: neutral | tense | surprised | angry | broken, tensionMin, tensionMax, assetPath }]

### session.events[]
GameMasterAgent와 Rule Engine이 만든 상태 변경은 이벤트로 저장하고 UI에 비동기 발행한다.
- eventId: string
- sessionId: string
- type: NOTE_FACT_ADDED | NOTE_CONTRADICTION_CANDIDATE_ADDED | EVIDENCE_UNLOCKED | TIMELINE_EVENT_REVEALED | TENSION_CHANGED | VISUAL_STATE_CHANGED | BOOKMARK_SUGGESTED
- source: character_agent | light_rule_check | game_master_agent | rule_engine | system
- payload: object
- visibility: public | internal
- applied: boolean
- createdAt: ISO datetime

### case.storyline.acts[]
- actId: intro | alibi_collection | first_break | motive_reveal | final_accusation
- title: string
- objective: string
- entryCondition: "start" | contradiction id | pressure threshold descriptor
- focusSuspectIds: string[]
- suggestedQuestionIntents: string[] — 선택지가 아니라 대화 입력 예시/의도. 버튼 강제 선택지로 쓰지 않음
- requiredClueIds: string[]
- playerHint: 공개 가능한 진행 힌트
- completionCondition: string

### case.storyline.timeline[]
공개 타임라인 항목. 전체 사건 타임라인 중 플레이어에게 보여도 되는 항목만 노출한다. hidden=true 항목은 API에 노출하지 말 것.
- time: string
- title: string
- description: string
- sourceType: evidence | record | statement | inference
- sourceId: string
- hidden?: boolean
- unlockCondition?: string

### case.storyline.cluePaths[]
모순을 찾는 추리 경로. `secretNote`는 공개 API에 노출하지 말 것.
- pathId: string
- title: string
- objective: string
- steps: [{ order, type, id, prompt }]
- resolvesContradictionId?: string
- unlocks: string[]
- secretNote?: string

### case.storyline.currentObjectiveRules[]
세션 상태에서 현재 목표를 계산하기 위한 공개 룰.
- priority: number
- when: { missingContradictionId?: string, discoveredContradictionId?: string, pressureAtLeast?: { suspectId, value } }
- objective: string
- actId: string

## Service Responsibilities

### BE
- Pydantic models 추가: Opening, StoryAct, TimelineEvent, CluePath, ObjectiveRule, Scenario, CharacterTimeline, VisualAssets, Storyline.
- `case_001.json`에 위 구조 작성.
- `visible_session_payload`에 `opening`, `storyline`, `currentObjective`, `currentActId`, `visibleTimeline`, `visualState`, `lastEventId` 추가.
- 공개 payload sanitization: `secret`, `isCulprit`, `solution`, `truthSummary`, `culpritTheory`, `privateMotive`, hidden timeline, cluePath.secretNote, characterTimeline의 비공개 event는 노출 금지.
- Event Processor 추가: GameMasterAgent의 `proposedEvents[]`를 검증하고 session event store에 저장한 뒤 SSE/WebSocket으로 발행.
- `GET /api/v1/sessions/{session_id}/events` SSE endpoint 추가.
- 테스트 추가:
  - case/session payload에 storyline이 있음.
  - hidden/secret/solution/isCulprit/secretNote 노출 없음.
  - 모순 해결 전/후 currentObjective/currentActId가 바뀜.
  - GameMasterAgent proposed event가 검증 후 event store에 저장되고 SSE payload로 직렬화됨.

### FE
- API types/normalizer에 storyline/currentObjective/currentActId/visibleTimeline/visualState 추가.
- 첫 화면 상단 또는 중앙에 “현재 목표” 카드 추가.
- 별도 “스토리/타임라인” 패널 추가: act progression + 공개 timeline + clue path 안내.
- 질문 선택지 UI가 아니라 대화 입력창을 기본으로 하고, suggestedQuestionIntents는 placeholder/예시 문장/자동완성 힌트로만 사용한다.
- visualState에 따라 background image와 캐릭터 이미지를 교체한다. 예: neutral, tense, surprised, angry, broken.
- `GET /api/v1/sessions/{sessionId}/events` SSE를 구독하고 NOTE/EVIDENCE/TIMELINE/TENSION/VISUAL 이벤트를 비동기 반영한다.
- HTTP 대화 응답은 즉시 대화창에 표시하고, GameMasterAgent가 만든 수첩/증거/배경 변경은 SSE 이벤트 도착 시 반영한다.
- 빌드 통과.

### AI
- dialogue/hint/summary/ending 요청에서 공개 storyline context, character timeline 공개 항목, visualState를 받을 수 있게 schema를 확장하되 extra hidden truth는 사용하지 않도록 guard 유지.
- CharacterAgent는 캐릭터 성격, 개인 타임라인 공개/해금 항목, 현재 긴장도에 맞춰 답변한다.
- LightRuleCheck는 실제 타임라인/허용 진술과 충돌하는 이상 대화, 정답 누설, 감정 상태 불일치를 검증한다.
- GameMasterAgent는 대화에서 드러난 정보와 timeline/evidence/statement 연결을 `proposedEvents[]`로 구조화한다. 실제 사건노트 기록/증거 해금/visualState 변경은 Backend Event Processor가 검증 후 수행한다.
- hint는 currentObjective와 공개 timeline을 활용해 다음 행동을 말하되 정답/범인 직접 노출 금지.
- 테스트: hidden fields/solution/private timeline 없이도 동작, extra secret fields 무시.

## Golden Route Verification

1. docker compose up -d --build
2. GET /api/v1/cases/case_001: public storyline present, no secret fields.
3. POST /api/v1/sessions: currentObjective = 알리바이 수집/진술 확보 계열.
4. POST dialogue message: suspectId=char_hanseoyeon, text="22시 이후 어디에 있었나요?".
5. AI 응답이 CharacterAgent → LightRuleCheck → GameMasterAgent 순서로 처리되고, GameMasterAgent가 `proposedEvents[]`를 반환한다.
6. POST contradiction st_hanseoyeon_room_2200 + ev_study_entry_log: correct, currentActId advances toward motive_reveal/first_break.
7. BE Event Processor가 NOTE_FACT_ADDED 또는 VISUAL_STATE_CHANGED를 저장하고 SSE로 발행한다.
8. FE at http://127.0.0.1:8080 shows current objective, storyline/timeline panel, dialogue input, SSE 기반 수첩 업데이트, visualState 기반 배경/캐릭터 이미지.
