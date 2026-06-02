# BE Implementation Notes

## 목적

FastAPI 기반 Backend API를 구현한다. Backend는 게임 상태의 단일 진실 공급원이며, 대화 제한, 사건 진행, 시나리오/캐릭터별 타임라인, 룰 기반 모순 판정, visualState 산출, 저장/조회, AI Service 호출을 담당한다.

Python 의존성 관리는 `pyproject.toml`과 `uv.lock`을 기준으로 한다. Docker 런타임은 `uv sync --frozen --no-dev`로 lock 파일에 고정된 의존성을 설치한다.

## 책임 범위

| 영역 | 구현사항 |
| --- | --- |
| Session API | 새 게임 생성, 세션 조회, 진행 상태 저장 |
| Case Engine | 사건 데이터 로딩, 전체 시나리오/캐릭터별 타임라인, 증거/진술 해금 조건 관리 |
| Rule Engine | 모순 판정, 압박 수치, 최종 범인 지목 판정 |
| AI Gateway | AI Service 호출, timeout/retry/비정상 응답을 명시적 degraded 상태로 매핑 |
| Event Processor | GameMasterAgent/RuleEngine 이벤트 검증, event store 저장, SSE/WebSocket 발행 |
| Persistence | 세션 상태, 대화 기록, 발견 단서, 이벤트 로그 저장 |

## 권장 구조

```text
BE/
  app/
    main.py
    api/
      routes_cases.py
      routes_sessions.py
      routes_ai.py
    core/
      config.py
      errors.py
    domain/
      case_engine.py
      rule_engine.py
      event_processor.py
      models.py
    infra/
      case_repository.py
      session_repository.py
      event_repository.py
      ai_client.py
    schemas/
      cases.py
      sessions.py
      verdicts.py
```

## 주요 API

| Method | Path | 설명 | 우선순위 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health` | 상태 확인 | P0 |
| `GET` | `/api/v1/ready` | Backend + AI Service readiness 확인. AI 장애 시 `status=degraded`를 반환한다. | P0 |
| `GET` | `/api/v1/cases` | 사건 목록 조회 | P0 |
| `GET` | `/api/v1/cases/{case_id}` | 사건 개요 조회 | P0 |
| `POST` | `/api/v1/sessions` | 새 세션 생성 | P0 |
| `GET` | `/api/v1/sessions/{session_id}` | 세션 상태 조회 | P0 |
| `POST` | `/api/v1/sessions/{session_id}/dialogue` | 자연어 대화 입력 및 답변 생성 | P0 |
| `POST` | `/api/v1/sessions/{session_id}/questions` | 기존 질문 ID 기반 호환 API. `questionId`를 받거나, FE 이전 구현 호환을 위해 `{ suspectId, questionText }` free-text payload를 `/dialogue`와 동일한 처리 흐름으로 라우팅한다. 신규 FE는 `/dialogue` 사용 권장. | P0 |
| `POST` | `/api/v1/sessions/{session_id}/accusation` | 최종 범인 지목 | P0 |
| `POST` | `/api/v1/sessions/{session_id}/notes` | 추리 노트 저장 | P1 |
| `POST` | `/api/v1/sessions/{session_id}/bookmarks` | 대화/진술/증거/기록 북마크 | P1 |
| `GET` | `/api/v1/sessions/{session_id}/summary` | 현재 노트/로그 요약 조회 | P1 |
| `GET` | `/api/v1/sessions/{session_id}/hint` | 현재 진행 상태 기반 힌트 조회 | P1 |
| `GET` | `/api/v1/sessions/{session_id}/ending` | 최종 지목 이후 엔딩 해설 조회 | P1 |
| `POST` | `/api/v1/sessions/{session_id}/notes/summary` | 추리 노트 요약 요청 | P1 |
| `GET` | `/api/v1/sessions/{session_id}/events` | SSE 기반 세션 이벤트 스트림 | P0 |
| `POST` | `/api/v1/sessions/{session_id}/debug/pressure` | dev-only 캐릭터 압박/긴장 수치 조정. `BE_DEBUG_TOOLS_ENABLED=true` 필요 | DEV |
| `POST` | `/api/v1/sessions/{session_id}/debug/unlock` | dev-only 공개 evidence/relation/timeline/note unlock. `BE_DEBUG_TOOLS_ENABLED=true` 필요 | DEV |

## 핵심 도메인 규칙

| 규칙 | 설명 |
| --- | --- |
| 대화 횟수 | 플레이어가 대화 메시지를 전송하면 세션의 `remainingQuestions` 또는 `remainingDialogues`를 1 감소시킨다. |
| 반복 질문 | 동일 용의자에게 같은 의미의 질문을 다시 하면 반복 질문으로 기록하고 추가 정보 제공 여부는 사건 데이터가 결정한다. |
| 캐릭터별 타임라인 | 각 용의자의 실제 행적, 주장한 알리바이, 거짓말/누락, 감정 변화, 연결 증거를 사건 데이터에 보존한다. 공개 payload에는 해금된 공개 항목만 포함한다. |
| visualState | 현재 장소, act, 용의자 압박/긴장도, 감정 상태에 따라 backgroundId와 characterImageState를 계산한다. |
| 해금 | 특정 모순 정답 또는 압박 수치 도달 시 새 진술, 증거, 공개 타임라인 항목을 해금한다. |
| 판정 우선순위 | 정답 여부는 Rule Engine이 결정하며 AI 응답은 판정을 덮어쓸 수 없다. |
| 최종 지목 | 범인 ID만이 아니라 필수 모순/증거 포함 여부를 함께 평가한다. |

## 모순 판정 결과

```json
{
  "verdict": "correct",
  "reasonCode": "time_location_conflict",
  "pressureDelta": 40,
  "unlockedIds": ["statement_009"],
  "message": "서재 출입 기록과 방에 있었다는 진술이 충돌합니다."
}
```

`verdict` 값:

| 값 | 의미 |
| --- | --- |
| `correct` | 핵심 또는 일반 모순 정답 |
| `partial` | 관련성은 있으나 필수 근거가 부족 |
| `insufficient` | 방향은 맞지만 연결 근거가 약함 |
| `wrong` | 사건 그래프상 관련 없는 조합 |

## FE 연동 응답 계약

세션 조회/갱신 API는 동일한 기본 payload를 반환한다. FE는 `remainingQuestions` 또는 `remainingDialogues`, `phase`, `caseFile`, `notebook`, `contradictions`, `relationMap`, `suspects[].pressureState`, `suspects[].tensionLevel`, `suspects[].emotionalState`, `suspects[].speechStyle`, `suspects[].publicTimeline`, `dialogueLog`, `evidence`, `records`, `relations`, `statements`, `notes`, `bookmarks`, `discoveredContradictionIds`, `currentObjective`, `currentActId`, `visibleTimeline`, `visualState`, `lastEventId`를 상태에 반영한다. `caseFile`은 사건 파일 패널용 공개 사건 개요/목표/타임라인이고, `notebook`은 메모/북마크/증거 상세/진술 by suspect/질문 by suspect/모순/관계도 read model을 묶은 조사 노트북 view이다. `contradictions`는 `{ discoveredIds, discovered, candidates }` 형태의 공개 모순 상세이며 FE가 ID만으로 재구성하지 않도록 `title`, `suspectId`, `statementIds`, `evidenceIds`, `severity`, `reasonCode`, `displayText`, `submitEligible`을 제공한다. 모순 판정은 별도 `/contradictions` API가 아니라 `/dialogue`에서 플레이어 발화가 공개 진술/증거 조합으로 매핑될 때 BE Rule Engine이 결정적으로 수행하며, 응답의 `dialogueResult.contradictionResult`와 SSE로 반영한다. `relationMap`은 `{ centerCharacterId, nodes, edges }` 형태이며 edge는 `relationshipId`, `sourceCharacterId`, `targetCharacterId`, `label`, `description`, `conflict`, `unlocked`, `unlockState`, `evidenceRefs`, `statementRefs`, `recordRefs`를 제공한다. locked edge는 안정 ID와 source/target만 공개하고 conflict/private detail은 빈 값/placeholder로 마스킹한다.

메모 API는 `GET /sessions/{sessionId}/notes`, `POST /sessions/{sessionId}/notes`, `PUT /sessions/{sessionId}/notes/{noteId}`, `DELETE /sessions/{sessionId}/notes/{noteId}`를 지원한다. 생성/수정/삭제 응답은 갱신된 세션 payload와 `notebook.notes`를 포함하고, SSE에는 `NOTE_CREATED`, `NOTE_UPDATED`, `NOTE_DELETED`가 기록되어 FE가 local-only state 없이 재조회/반영할 수 있다. note link 대상은 현재 세션에서 visible한 statement/evidence/record만 허용한다.

대화 API는 기본 payload에 `answer`, `dialogueResult`, `proposedEventsApplied`, `visualState`를 추가한다. `message`는 추천 질문 문구와 정확히 일치하지 않아도 되며, BE는 선택된 suspect의 해금된 질문/진술 컨텍스트 중 관련성이 확인된 항목만 매핑한다. BE는 free-text를 `small_talk`, `case_question`, `timeline_question`, `evidence_question`, `pressure_followup`, `unmatched` 등으로 분류하며, greeting/small-talk/unmatched 입력은 질문을 소모하지 않고 `matchedQuestionId: null`, `consumedQuestion: false`를 반환한다. `10시부터 22시까지`, `22시까지`, `밤 10시 전후`, `그 시간에 뭐했어` 같은 broad Korean time-range/alibi 질문은 active suspect의 alibi/timeline context로 라우팅한다. 직전 답변에 대한 `왜 답변을 못해요`, `말이 된다고 생각해?` 같은 meta pressure follow-up은 최근 dialogue context와 공개 알리바리 statement를 묶어 `pressure_followup`으로 처리하고 질문 횟수를 소모하지 않는다. 키워드/시간/증거 컨텍스트 매칭이 없는 입력을 첫 번째 미질문 항목으로 맹목 fallback하지 않는다. BE가 AI에 전달하는 구조화 컨텍스트는 `currentActId`, `currentObjective`, `storyline.visibleTimeline`, 선택 캐릭터의 `publicProfile`, `speechStyle`, `publicTimeline`, `characterTimeline`, `characterKnowledgePack`, `pressureState`, `tensionLevel`, `tensionScore`, `emotionalState`, `expression`, visible statement/evidence/record IDs, 최근 dialogue summary, `visualState`, `allowedEventPolicy`를 포함한다. `characterKnowledgePack`은 Obsidian/LLMWiki CaseWiki를 컴파일한 형태의 public projection 계약으로, persona skill, `personaVariants`, BE가 tensionLevel/pressureState/emotionalState/tensionScore/recentDialogue/contradiction pressure로 선택한 `activePersonaOverlay`, claimed timeline/alibi statements, visible evidence/records/timeline, recent dialogue를 포함하고 `restrictedDataIncluded=false`를 보장한다. AI 3-Agent runtime은 typed `CharacterAgentInput -> DraftCharacterReply -> LightRuleCheckInput -> CheckedCharacterReply -> GameMasterAgentInput -> GameMasterProposal` 계약을 사용한다. CharacterAgent와 LightRuleCheck는 이벤트/상태 변경을 만들지 않고, GameMasterAgent만 공개 proposedEvents를 제안한다. AI Service가 timeout/비정상 응답/미설정으로 degraded 상태이면 BE는 503 `AI_SERVICE_DEGRADED`를 반환하고 질문 소모, dialogueLog 저장, note/event 생성, unlock 적용을 하지 않는다. GameMasterAgent는 공개 unlock/candidate 이벤트만 제안할 수 있고, `TENSION_CHANGED`는 BE 전용 이벤트다. Event Processor는 AI가 제안한 `TENSION_CHANGED`를 거부한다. `TENSION_CHANGED`는 Rule Engine이 검증한 신규 evidence+testimony/alibi 모순이 처음 발견될 때만 한 번 발행되며, 일반 대화/해금/재질문/중복 제출/AI degraded 경로에서는 압박 수치와 tension을 변경하지 않는다. `small_talk`/`unmatched`는 dialogue mode별 `allowedEventPolicy`와 Event Processor 검증을 통과하지 않는 한 `NOTE_FACT_ADDED`를 만들지 않는다.

요청 본문:

```json
{
  "suspectId": "char_hanseoyeon",
  "message": "22시 이후 어디에 있었나요?"
}
```

```json
{
  "answer": "저는 22시 이후 계속 제 방에 있었어요.",
  "dialogueResult": {
    "messageId": "msg_001",
    "suspectId": "char_hanseoyeon",
    "dialogueMode": "case_question",
    "intent": "case_question",
    "matchedQuestionId": "q_hanseoyeon_alibi",
    "matchedIntentId": "q_hanseoyeon_alibi",
    "consumedQuestion": true,
    "previousRemainingQuestions": 11,
    "remainingQuestions": 10,
    "remainingQuestionsDelta": -1,
    "fallbackUsed": false,
    "provider": "ai-service",
    "safety": {"status": "checked"},
    "proposedEventsCount": 1,
    "appliedEventsCount": 1,
    "emotionalState": "wary",
    "tensionLevel": "low"
  },
  "proposedEventsApplied": ["evt_001", "evt_002"],
  "visualState": {
    "backgroundId": "mansion_study_night",
    "characterImageState": "wary",
    "emotionalState": "wary",
    "expression": "wary",
    "pressureState": "normal",
    "tensionLevel": "low",
    "tensionScore": 0
  }
}
```

모순 판정은 대화 API의 일부다. BE는 플레이어 발화에서 공개된 진술/증거/타임라인 참조를 매핑한 뒤 Rule Engine에 제출한다. 신규 `correct`일 때만 압박 수치를 올리고 `TENSION_CHANGED`를 SSE로 발행할 수 있으며, `unlockedIds`를 통해 새 진술/질문/기록/관계를 공개한다. 중복 `correct`, `partial`, `insufficient`, `wrong`은 압박 수치를 올리지 않는다. 응답의 `dialogueResult.contradictionResult.newlyDiscovered`와 `pressureDelta`로 idempotent tension 적용 여부를 확인할 수 있다.

최종 지목 API는 기본 payload에 단순한 `accusationResult`를 추가한다. FE는 플레이어가 작성한 `motive`, `method` 텍스트를 함께 보낼 수 있다. 이 텍스트는 `submittedMotive`, `submittedMethod`로 보존하지만, 정답 판정은 기존처럼 범인 ID와 `requiredContradictionIds`, `requiredEvidenceIds`, `requiredStatementIds` 포함 여부만으로 평가한다. 공개 결과는 `{ verdict, correct, message, submittedMotive, submittedMethod }`만 제공하고, 누락 ID 목록 같은 디버그성 상세는 응답에 싣지 않는다.

```json
{
  "suspectId": "char_hanseoyeon",
  "motive": "상속 비율 변경으로 인한 갈등",
  "method": "서재 출입 후 정전 시간을 이용한 현장 조작",
  "evidenceIds": ["ev_study_entry_log", "ev_torn_will"],
  "contradictionIds": ["con_room_claim_vs_entry_log", "con_inheritance_motive"],
  "statementIds": ["st_hanseoyeon_room_2200", "st_hanseoyeon_no_reason"]
}
```

비동기 이벤트 스트림:

```text
GET /api/v1/sessions/{session_id}/events
Accept: text/event-stream
Last-Event-ID: evt_001
```

```text
event: NOTE_FACT_ADDED
id: evt_002
data: {"sessionId":"session_001","payload":{"text":"한서연은 22시 이후 방에 있었다고 주장했다."}}
```

지원 이벤트 타입: `NOTE_FACT_ADDED`, `NOTE_CONTRADICTION_CANDIDATE_ADDED`, `EVIDENCE_UNLOCKED`, `TIMELINE_EVENT_REVEALED`, `TENSION_CHANGED`, `VISUAL_STATE_CHANGED`, `BOOKMARK_SUGGESTED`, `VISUAL_REACTION_SUGGESTED`, `DEBUG_SESSION_UPDATED`. `NOTE_FACT_ADDED`는 visible statement/evidence/record/timeline source ID가 검증될 때만 적용되며, `NOTE_CONTRADICTION_CANDIDATE_ADDED`는 contradictionId의 required statement/evidence가 현재 세션에 공개된 경우에만 적용된다. `TENSION_CHANGED`는 AI proposedEvents 허용 타입이 아니며 BE가 신규 검증 모순에 대해 생성한 이벤트만 유효하다.

Debug endpoints는 기본 비활성화이며 `BE_DEBUG_TOOLS_ENABLED=true`일 때만 사용한다. `/debug/pressure`는 `{ suspectId, pressure }`로 BE 세션의 공개 압박 수치를 갱신하고 `TENSION_CHANGED`, `VISUAL_STATE_CHANGED`, `DEBUG_SESSION_UPDATED` SSE를 발행한다. `/debug/unlock`은 `{ target: "evidence" | "relations" | "timeline" | "notes" | "all" }`을 받아 공개 read model에 표시 가능한 증거/관계/기록/진술/질문/타임라인만 해금하고 `EVIDENCE_UNLOCKED`, `NOTE_CREATED`, `DEBUG_SESSION_UPDATED` SSE를 발행한다. Debug 응답도 일반 세션 payload와 동일한 public builder를 통과하므로 `secret`, `solution`, `isCulprit`, private motive/action은 노출하지 않는다.

노트/북마크/요약/힌트/엔딩 응답:

| API | 추가 응답 필드 |
| --- | --- |
| `POST /notes` | 기본 세션 payload + `note` |
| `POST /bookmarks` | 기본 세션 payload + `bookmark` |
| `GET /summary` | `{ sessionId, caseId, summary }` |
| `POST /notes/summary` | `{ sessionId, caseId, summary }` |
| `GET /hint` | `{ sessionId, caseId, hint }` |
| `GET /ending` | `{ sessionId, caseId, verdict, ending, accusation, usedQuestions, discoveredContradictionIds }` |

공개 payload의 `suspects`에는 `secret`, `isCulprit`, `privateMotive`, 비공개 timeline event를 포함하지 않는다.

Docker 실행:

```bash
docker build -t detective-agent-be .
docker run --rm -p 8000:8000 detective-agent-be
```

## AI Service 연동

Backend는 AI Service를 내부 서비스로만 호출한다.

| 호출 목적 | AI Service Endpoint | 실패 시 처리 |
| --- | --- | --- |
| 대화 생성/검증/이벤트 제안 | `POST /internal/v1/dialogue/respond` | 503 `AI_SERVICE_DEGRADED`, 세션 미변경, FE 표시용 degraded reason 반환 |
| 힌트 생성 | `POST /internal/v1/hints` | AI degraded 안내 반환, deterministic game state는 변경하지 않음 |
| 노트 요약 | `POST /internal/v1/notes/summary` | AI degraded 안내 반환, note/session state는 변경하지 않음 |
| 엔딩 해설 | `POST /internal/v1/endings/explain` | 판정 결과는 BE deterministic 결과를 유지하고 AI 해설 degraded 안내 반환 |

## 저장소

MVP 초기에는 파일 기반 사건 데이터와 SQLite 세션 저장을 허용한다. 이후 PostgreSQL로 이전할 수 있도록 repository 인터페이스를 분리한다.

| 데이터 | MVP 저장 방식 |
| --- | --- |
| 사건 데이터 | JSON 파일. 전체 시나리오, 공개 storyline, 캐릭터별 타임라인, visualAssets 포함 |
| 세션 상태 | SQLite 또는 파일 |
| 대화 기록 | 세션 상태에 포함 |
| 발견 단서 | 세션 상태에 포함 |
| 이벤트 로그 | SQLite 또는 파일. SSE 재연결 복구를 위해 eventId 순서 보존 |

## 비포함

- Backend는 LLM을 직접 호출하지 않는다.
- Backend는 AI 응답을 정답 판정의 근거로 사용하지 않는다.
- 계정, 결제, 랭킹, 멀티플레이는 MVP 범위가 아니다.
