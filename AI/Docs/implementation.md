# AI Implementation Notes

## 목적

FastAPI + LangGraph 기반 AI Service를 구현한다. AI Service는 CharacterAgent, LightRuleCheck, GameMasterAgent를 순차 실행해 캐릭터 대화 생성, 이상 대화 검증, 사건노트 이벤트 제안을 담당하며, 게임 판정과 실제 상태 변경의 최종 권한은 Backend Rule Engine/Event Processor에 둔다.

## 책임 범위

| 영역 | 구현사항 |
| --- | --- |
| CharacterAgent | Backend가 허용한 사건 사실, 용의자 성격, 긴장도를 바탕으로 캐릭터 답변 생성 |
| Hint Generation | 현재 세션 상태에서 스포일러를 제한한 힌트 생성 |
| GameMasterAgent | 대화에서 나타난 캐릭터 정보, 단서 후보, 모순 후보를 `proposedEvents[]`로 구조화 |
| Ending Explanation | 최종 판정 결과를 자연어 엔딩 해설로 변환 |
| LightRuleCheck | 캐릭터가 이상한 대화, 설정 위반, 정답 누설, 감정 상태 불일치를 보이는지 검증 |
| Deterministic Fallback | 외부 LLM 키나 provider 장애가 있어도 로컬 문장 생성으로 응답 |

## 권장 구조

```text
AI/
  app/
    main.py
    api/
      internal_routes.py
    graph/
      dialogue_graph.py
      hint_graph.py
      summary_graph.py
      ending_graph.py
    prompts/
      dialogue.py
      hint.py
      summary.py
      ending.py
    schemas/
      dialogue.py
      hints.py
      notes.py
      endings.py
    core/
      config.py
      llm.py
```

## LangGraph 워크플로우

### Dialogue Graph

| 노드 | 역할 |
| --- | --- |
| `load_context` | Backend가 전달한 사건 상태, 용의자 상태, 허용 진술, 긴장도, 플레이어 질문 로드 |
| `CharacterAgent` | 선택된 캐릭터의 성격/말투/현재 감정 상태를 반영해 답변 생성 |
| `LightRuleCheck` | 생성 답변이 이상한 대화, 사건 설정 위반, 정답 누설, 감정 상태 불일치를 포함하는지 검증 |
| `GameMasterAgent` | 검증된 대화에서 드러난 캐릭터 정보, 단서, 모순 후보를 `proposedEvents[]`로 구조화. DB/session/UI를 직접 변경하지 않음 |
| `format_response` | Backend 응답 스키마에 맞게 답변, safety, proposedEvents, visualState를 정리 |

### Hint Graph

| 노드 | 역할 |
| --- | --- |
| `inspect_progress` | 발견한 증거와 미발견 핵심 모순 비교 |
| `select_hint_level` | 힌트 강도 선택 |
| `generate_hint` | 직접 정답을 말하지 않는 힌트 생성 |
| `guard_spoiler` | 범인, 핵심 증거 직접 노출 방지 |

## 내부 API

| Method | Path | 설명 | 우선순위 |
| --- | --- | --- | --- |
| `GET` | `/health` | 상태 확인 및 현재 생성 provider 확인 | P0 |
| `POST` | `/internal/v1/dialogue/respond` | CharacterAgent 답변 생성 + LightRuleCheck 검증 + GameMasterAgent 이벤트 제안 | P0 |
| `POST` | `/internal/v1/hints` | 힌트 생성 | P1 |
| `POST` | `/internal/v1/notes/summary` | 추리 노트 요약 | P1 |
| `POST` | `/internal/v1/endings/explain` | 엔딩 해설 생성 | P1 |

## API 계약 원칙

| 원칙 | 설명 |
| --- | --- |
| Rule Engine 우선 | AI Service는 `verdict.result`, 해금, 압박, 질문 횟수, 최종 정답 여부를 재판정하지 않는다. |
| 승인 진술 범위 | 대화 생성은 `allowedStatement.text`를 기준 사실로 삼되, 공개 지식팩 안에서 캐릭터 감정, 관계 해석, 기억의 말투, 장면 분위기 같은 비권위적 연결 조직은 LLM이 생성할 수 있다. |
| 실패 격리 | LLM 호출이 실패하면 deterministic fallback으로 대체해 AC-008을 만족한다. |
| 출처 보존 | 힌트와 요약은 Backend가 전달한 `allowedClues`, `dialogueLogs`, `discoveredEvidence`만 사용한다. |
| 안전 메타데이터 | 모든 응답은 `safety.fallbackUsed`, `safety.repaired`, `safety.blockedReason`으로 fallback/보정 사유를 노출한다. |
| 상태 변경 금지 | AI Service는 세션/DB/UI 상태를 직접 변경하지 않고 `proposedEvents[]`만 반환한다. Backend Event Processor가 검증 후 적용/발행한다. |

## Bounded Generative Autonomy

AI의 목표는 모든 발화를 규칙으로 스크립트하는 것이 아니라, 고정된 핵심 사건을 훼손하지 않는 범위에서 캐릭터별 맥락과 현장감을 생성하는 것이다. 실패한 dogfood 발화를 고칠 때는 먼저 CaseWiki/CharacterKnowledgePack, public timeline, relationship/evidence projection, retrieval/ranking, persona overlay, prompt contract를 개선한다. hard guard는 진짜 invariant 위반, private leak, 상태 권한 침범에만 추가한다.

| 구분 | 예시 | AI 처리 방향 |
| --- | --- | --- |
| Hard Invariants | 범인, 핵심 수법, 핵심 시간선, 결정적 증거의 진실, 엔딩 기준, private/public boundary, 세션 상태/해금/압박/판정 권한 | LightRuleCheck/BE/EventProcessor가 차단 또는 거부한다. AI는 제안만 하고 권위 상태를 바꾸지 않는다. |
| Soft Constraints | 캐릭터별 공개 지식, knownBy/unknownBy, 신뢰도, 시점별 인식, tension/persona, public relationship, allowedEventPolicy, 현재 질문 의도 | LLM의 생성 공간을 좁히는 guidance로 사용한다. 부족하면 지식팩/검색/프롬프트를 보강한다. |
| Generative Freedom | 말투, 감정 질감, 작은 사회적 추론, 관계 긴장 표현, 의심 표현, 기억의 paraphrase, 장면 flavor, canon과 충돌하지 않는 비권위적 connective tissue | 공개 projection 안에서 허용한다. 필요하면 NOTE/OBSERVATION/RUMOR/INTERPRETATION 같은 저신뢰 후보로 제안하고 BE가 검증한다. |

LightRuleCheck는 lightweight anomaly/leakage/invariant checker이다. 대화를 스크립트하는 rule engine이 아니며, 정상적인 창의성을 막는 방향으로 확장하지 않는다. GameMasterAgent는 LLM 기반 contextual interpreter로, surfaced dialogue에서 note/clue/relationship 후보를 `proposedEvents[]`로 구조화한다. 최종 적용, visibility, persistence, TensionPolicy, SSE는 항상 BE 권한이다.

Future-fix rubric:

- main truth/private boundary/state authority 위반이면 guard 또는 BE validator를 추가/수정한다.
- 대화가 얕거나 관계/맥락을 놓치면 hard guard가 아니라 wiki/projection/retriever/persona/prompt를 개선한다.
- 흥미롭지만 비권위적인 작은 연결 조직은 truth mutation으로 저장하지 말고 ephemeral flavor 또는 낮은 confidence의 observation/rumor/interpretation 후보로 둔다.
- 새 validator를 추가하기 전에 context-enrichment-first 검토를 남긴다.

## Allowed Data 경계

알 수 없는 extra field는 Pydantic 호환성을 위해 수신은 허용하지만 생성에는 사용하지 않는다.

| API | 생성에 사용하는 필드 |
| --- | --- |
| Dialogue | `suspect.pressureState`, `suspect.tensionLevel`, `suspect.publicPersona`, `allowedStatement.id/text`, `question.text` 또는 `playerMessage.text`, `style.tone/maxLength`, `visualState.backgroundId/characterImageState/emotionalState`, `storyline.currentObjective/currentActId/visibleTimeline/characterTimelines.publicPersona/events(public)`, `characterTimeline.publicPersona/events(public)`, `allowedEventPolicy.allowedTypes/relatedEvidenceIds/relatedTimelineEventIds/relatedStatementIds`, `revealAllowed` |
| Hint | `allowedClues`, `storyline.currentObjective/currentActId/publicPremise/openingObjective/visibleTimeline/characterTimelines.publicPersona/events(public)`, `characterTimelines.publicPersona/events(public)`, `discoveredEvidence.id/name`, `visualState.backgroundId/characterImageState/emotionalState`, `hintLevel`, `revealAllowed` |
| Summary | `storyline.currentObjective/currentActId/publicPremise/openingObjective/visibleTimeline/characterTimelines.publicPersona/events(public)`, `characterTimelines.publicPersona/events(public)`, `dialogueLogs.speaker/text/id/statementId`, `discoveredEvidence.id/name/description`, `visualState.backgroundId/characterImageState/emotionalState`, `maxItems`, `revealAllowed` |
| Ending | `storyline.currentObjective/currentActId/publicPremise/openingObjective/visibleTimeline/characterTimelines.publicPersona/events(public)`, `characterTimelines.publicPersona/events(public)`, `verdict.result/label/reason/missedEvidenceIds/revealAllowed`, `visualState.backgroundId/characterImageState/emotionalState`, `culpritName`은 reveal 허용 시에만, `usedQuestionCount`, `foundCoreContradictionCount` |

Dialogue는 `storyline.currentActId`와 긴장도/visualState/emotionalState를 말투/이미지 상태 선택에만 사용하고, 출력 사실은 항상 Backend가 허용한 사건 사실과 `allowedStatement.text`로 제한한다. Hint와 Summary는 `visibleTimeline` 중 `hidden=true`로 들어온 항목을 방어적으로 건너뛴다. `characterTimeline`/`characterTimelines`는 공개 persona와 public event의 claimed 정보만 생성 컨텍스트로 사용할 수 있으며 `privateMotive`, 실제 행적, `isLie`, `secret`, `solution`, `isCulprit`, `secretNote` 같은 extra 필드는 수신되어도 생성/이벤트 제안/로그에 사용하지 않는다.

## Dialogue 요청 예시

```json
{
  "sessionId": "session_001",
  "caseId": "case_001",
  "suspect": {
    "id": "suspect_001",
    "name": "한서연",
    "role": "조카",
    "pressureState": "normal"
  },
  "playerMessage": {
    "id": "msg_001",
    "text": "그날 저녁 9시 이후 어디에 있었나요?"
  },
  "allowedStatement": {
    "id": "statement_001",
    "text": "저는 22:00에 제 방에 있었어요."
  },
  "style": {
    "tone": "calm_defensive",
    "maxLength": 180
  },
  "visualState": {
    "backgroundId": "mansion_study_night",
    "characterImageState": "tense"
  },
  "allowedEventPolicy": {
    "allowedTypes": ["NOTE_FACT_ADDED", "NOTE_CONTRADICTION_CANDIDATE_ADDED", "BOOKMARK_SUGGESTED"],
    "relatedEvidenceIds": ["ev_study_entry_log"]
  },
  "requestId": "req_001"
}
```

## Dialogue 응답 예시

```json
{
  "statementId": "statement_001",
  "text": "저는 그 시간에 제 방에 있었어요. 누가 봤든 말든, 거짓말할 이유가 없잖아요?",
  "proposedEvents": [
    {
      "type": "NOTE_FACT_ADDED",
      "payload": {"text": "한서연은 22시 이후 계속 방에 있었다고 주장", "sourceStatementId": "statement_001"}
    },
    {
      "type": "NOTE_CONTRADICTION_CANDIDATE_ADDED",
      "payload": {"text": "서재 출입 기록과 비교 필요", "relatedEvidenceIds": ["ev_study_entry_log"]}
    }
  ],
  "visualState": {
    "backgroundId": "mansion_study_night",
    "characterImageState": "tense"
  },
  "safety": {
    "leaksSolution": false,
    "violatesCaseFacts": false,
    "blockedTerms": [],
    "fallbackUsed": false,
    "repaired": false,
    "blockedReason": null
  }
}
```

## 안전 규칙

| 규칙 | 설명 |
| --- | --- |
| 정답 누설 금지 | Backend가 `revealAllowed`를 주지 않으면 범인, 동기, 핵심 모순을 직접 말하지 않는다. |
| 사건 사실 변경 금지 | 전달받은 `allowedStatement`와 충돌하는 새 사실을 만들지 않는다. |
| 판정 변경 금지 | `correct`, `wrong` 같은 판정은 Backend 결과를 그대로 설명만 한다. |
| 근거 출처 유지 | 요약과 proposedEvents에는 실제 대화 로그, 허용 진술, 증거 ID에 있는 내용만 포함한다. |
| 이벤트 제안 제한 | GameMasterAgent는 `NOTE_*`, `NOTE_CONTRADICTION_CANDIDATE_ADDED`, `BOOKMARK_SUGGESTED`처럼 공개 ID로 검증 가능한 기록/후보 이벤트만 제안한다. `EVIDENCE_UNLOCKED`, `VISUAL_STATE_CHANGED`, `TENSION_CHANGED`, pressure 변경, verdict 변경은 AI가 제안하지 않는다. |

## 모델 선택

MVP에서는 비용과 지연을 줄이기 위해 deterministic fallback을 기본값으로 사용한다. 외부 LLM provider는 `app.core.llm.get_llm()` 인터페이스 뒤에 추가할 수 있으며, provider 장애는 그래프 내부에서 fallback으로 복구한다.

## Docker 실행

`AI/Dockerfile`은 다음 명령으로 서비스를 시작한다.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

검증 명령:

```bash
pytest -q
docker build -t detective-ai-service .
```

## 비포함

- AI Service는 세션 상태를 영구 저장하지 않는다.
- AI Service는 사건 원본 데이터, 세션 DB, UI 상태를 직접 수정하지 않는다.
- AI Service는 FE에서 직접 호출하지 않는다.
- 대화형 입력은 지원하지만, 사건 그래프 밖의 무제한 자유 채팅은 MVP 범위가 아니다.
