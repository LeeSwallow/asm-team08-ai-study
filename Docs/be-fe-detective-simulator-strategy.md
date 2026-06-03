# BE/FE Detective Simulator Strategy

> 목적: 현재 BE/FE 전략을 유지하되, 선택지 퀴즈나 챗봇이 아니라 “상태가 살아 움직이는 추리게임 시뮬레이터”로 완성한다.

## 1. 제품 정의

이 프로젝트의 핵심은 자연어 심문을 통해 용의자의 진술, 증거, 타임라인, 관계, 압박 상태가 비동기적으로 변하는 단일 화면 수사 시뮬레이터다.

게임 루프는 다음과 같다.

1. 플레이어가 특정 용의자를 선택하고 자연어로 질문한다.
2. BE가 질문을 공개 사건 지식, 진술, 증거, 타임라인, 최근 대화 맥락에 매핑한다.
3. BE 내부 AI pipeline이 `CharacterAgent -> LightRuleCheck -> GameMasterAgent` 순서로 답변과 `proposedEvents`를 만든다.
4. BE Event Processor가 proposed event를 검증하고 authoritative session state만 변경한다.
5. FE는 HTTP 응답과 SSE 이벤트를 reducer로 반영해 증거/노트/모순/압박/visualState를 갱신한다.
6. 플레이어는 발견한 모순과 근거를 통해 압박을 올리고 최종 지목을 제출한다.

불변 원칙:

- FE는 정답/비밀/범인 정보를 절대 갖지 않는다.
- AI는 답변과 공개 이벤트 제안만 한다. 정답 판정과 상태 변경 권위는 BE에 있다.
- local mock/canned fallback은 개발 보조일 뿐 production-ready 검증 기준이 아니다.
- UI는 `FE/target/chatgpt-shared-detective-interface.png`에 가까운 noir 수사 데스크여야 한다.

## 2. 현재 확인한 기반

검증한 파일:

- `Docs/implementation-overview.md`
- `Docs/architecture-quality-gates.md`
- `Docs/service-contract-dialogue-story.md`
- `BE/Docs/implementation.md`
- `FE/Docs/implementation.md`
- `BE/app/api/routes_sessions.py`
- `BE/app/application/dialogue_service.py`
- `BE/app/domain/rule_engine.py`
- `FE/src/App.tsx`
- `FE/src/api.ts`
- `FE/src/types.ts`

현재 상태:

- BE에는 `/sessions`, `/dialogue`, `/events` SSE, notes, bookmarks, debug, accusation 기반이 있다.
- DialogueService는 story progress, allowedEventPolicy, turnInterpretation, contradiction judge, AI payload, EventProcessor를 이미 엮고 있다.
- RuleEngine은 질문 소모, 모순 판정, 압박 상승, 최종 지목 판정의 deterministic authority를 갖고 있다.
- FE App은 이미 Header/SuspectPanel/InterrogationStage/EvidencePanel/SystemFlowStrip 등으로 분리되어 있고 API adapter와 hook 기반이다.
- FE API는 API 실패 시 non-local session에서는 degraded 표시를 하고 세션을 가짜로 진전시키지 않는 방향으로 되어 있다.

실행 검증:

- `BE`: `pytest -q` -> 44 passed, 431 warnings
- `FE`: `npm run build` -> 성공, Vite build 완료

## 3. 핵심 문제 정의

현재 구조는 “시뮬레이터가 될 수 있는 뼈대”는 있다. 하지만 게임으로 느껴지려면 아래 5개가 동시에 맞아야 한다.

### A. 대화가 사건을 실제로 움직여야 한다

단순 답변 생성이 아니라 매 turn마다 다음이 업데이트되어야 한다.

- visible statements
- notes/notebook
- contradiction candidates
- discovered contradictions
- suspect pressure/tension/emotion
- visualState background/character expression
- timeline/relation/evidence unlocks

### B. 모순 제기는 버튼 기능이 아니라 자연어 조사 루프의 일부여야 한다

FE의 모순 제출 UI는 결국 `/dialogue`로 공개 진술/증거 조합을 담은 자연어 발화를 보내야 한다. BE는 이를 deterministic RuleEngine으로 판정해야 한다.

### C. AI는 더 자유로워야 하지만 비밀을 알면 안 된다

답변이 얕아지는 문제는 guard를 계속 쌓아서 풀 문제가 아니다. 해결 방향은 다음이다.

- CaseWiki/characterKnowledgePack 강화
- personaVariants/activePersonaOverlay 강화
- recentDialogue + public timeline retrieval 강화
- allowedStatement를 “앵커”로 유지하되, safe connective tissue는 허용
- secret/private boundary는 leak guard와 public projection으로 보호

### D. FE는 BE-backed state가 보이는 수사 데스크여야 한다

첫 화면부터 다음이 보여야 한다.

- 용의자 카드의 압박/감정 상태
- 중앙 장면의 배경/캐릭터/말풍선
- 증거 grid와 locked/unlocked 상태
- 모순 후보 panel
- 최근 이벤트/노트 변화
- bottom AI pipeline strip

숨겨진 drawer 안에만 정보가 있으면 “시뮬레이터”가 아니라 “폼 UI”처럼 느껴진다.

### E. runtime 검증은 FE -> BE -> AI -> BE EventProcessor -> SSE -> FE까지 봐야 한다

단위 테스트와 FE build만으로는 충분하지 않다. Docker service refresh 후 실제 브라우저 또는 HTTP/SSE dogfood가 필요하다.

## 4. 목표 아키텍처

```text
FE
  App / InvestigationDesk
    useInvestigationSession
      api.ts
      eventSource subscription
      session reducer
    components
      SuspectPanel
      InterrogationStage
      EvidencePanel
      ContradictionPanel
      Notebook/Drawer
      SystemFlowStrip

BE
  routes_sessions.py
    thin endpoint only
  DialogueService
    load session/case
    classify/interpret turn
    build public AI payload
    call AI pipeline
    call EventProcessor
    persist session/events
  RuleEngine
    deterministic contradiction/accusation verdict
  EventProcessor
    validate proposedEvents
    mutate allowed public read model
    append SSE events
  CaseRepository/SessionRepository/EventRepository
    persistence boundary
  ai_engine
    CharacterAgent -> LightRuleCheck -> GameMasterAgent
```

## 5. BE 우선순위

### P0-1. EventProcessor를 게임 진행의 중심으로 고정

완료 기준:

- GameMasterAgent proposedEvents는 직접 state mutation을 못 한다.
- EventProcessor만 `NOTE_FACT_ADDED`, `NOTE_CONTRADICTION_CANDIDATE_ADDED`, `EVIDENCE_UNLOCKED`, `TIMELINE_EVENT_REVEALED`, `VISUAL_STATE_CHANGED`를 적용한다.
- rejected event는 diagnostics에 남기되 FE에 secret을 노출하지 않는다.

### P0-2. 자연어 turn interpreter 정확도 강화

완료 기준:

- 시간 질문: `22시`, `밤 10시`, `그 시간`, `그때 어디`를 suspect timeline/alibi와 매핑한다.
- 증거 질문: 공개 evidence title/alias/description을 matchedEvidenceIds로 매핑한다.
- 압박 follow-up: 직전 대화 맥락과 allowed statement를 근거로 처리하고 질문 횟수는 소모하지 않는다.
- unmatched를 첫 번째 질문으로 blind fallback하지 않는다.

### P0-3. Contradiction 판정을 플레이 루프에 통합

완료 기준:

- `/dialogue` 응답의 `dialogueResult.contradictionResult`가 FE에서 바로 표시 가능하다.
- 신규 correct만 pressure/tension을 올린다.
- 중복 correct/partial/insufficient/wrong은 pressure를 올리지 않는다.
- SSE로 `TENSION_CHANGED`, `VISUAL_STATE_CHANGED`, `NOTE_CONTRADICTION_CANDIDATE_ADDED`가 재현 가능하다.

### P0-4. Public projection/leak guard 회귀 테스트 강화

완료 기준:

- session payload, AI payload, SSE event, FE diagnostics에 forbidden refs가 없다.
- case JSON의 private/solution/isCulprit/privateTimeline이 public builder 밖으로 새지 않는다.

### P1. Case data를 실제 플레이 가능한 단서 경로로 보강

완료 기준:

- 각 용의자별 최소 2개 이상 public timeline claim
- 각 핵심 contradiction별 required statements/evidence/records가 자연어로 발견 가능
- 압박 단계별 persona/expression 변화
- final accusation에 필요한 근거가 UI에서 모두 수집 가능

## 6. FE 우선순위

### P0-1. 첫 화면을 target noir desk에 더 가깝게 고정

완료 기준:

- start/resume 이후 기본 화면에 suspect list, central scene, evidence grid, contradiction panel, bottom flow가 한 번에 보인다.
- active suspect card, red accent, panel borders, rainy study background, character art가 명확하다.
- placeholder/admin 느낌의 form layout이 없다.

### P0-2. SSE reducer를 session state의 실제 source로 사용

완료 기준:

- EventSource open/reconnect/error가 UI와 log에 보인다.
- `lastEventId` 기반 replay가 가능하다.
- 이벤트 타입별 reducer가 notes/evidence/tension/visualState/contradictions를 갱신한다.
- HTTP dialogue 응답과 SSE 이벤트가 충돌할 때 BE last state를 우선한다.

### P0-3. 모순 패널을 right column에 상시 노출

완료 기준:

- discovered/candidate contradictions가 right panel에서 즉시 보인다.
- statement/evidence 선택 상태가 명확하다.
- 제출은 local 판정이 아니라 `/dialogue`로 간다.
- 판정 결과가 중앙 dialogue와 contradiction panel에 모두 반영된다.

### P0-4. visualState 기반 캐릭터/배경 전환

완료 기준:

- `visualState.backgroundId`가 background asset을 고른다.
- `characterImageState`/`expression`이 캐릭터 asset 또는 overlay를 고른다.
- asset이 없으면 fallback을 쓰되 fallback 표시/로그가 있다.

### P1. Notebook/relations/final accusation을 BE-backed로 정리

완료 기준:

- notes CRUD는 BE API와 SSE로 동기화된다.
- relationMap은 public masked payload만 렌더링한다.
- final accusation은 suspect/motive/method/evidence/contradiction/statement IDs를 BE에 제출한다.

## 7. 통합 검증 시나리오

최소 commit-ready dogfood는 아래 순서가 필요하다.

1. Docker Compose affected services rebuild/recreate
2. `GET /api/v1/health`, `GET /api/v1/ready`
3. FE 접속 `http://127.0.0.1:8080/`
4. 새 세션 생성
5. 한서연에게 자연어 알리바이 질문
6. 응답이 AI/runtime diagnostics와 함께 표시되는지 확인
7. 관련 증거/진술 기반 모순 제기
8. `dialogueResult.contradictionResult` 확인
9. SSE로 note/contradiction/tension/visualState 변화 확인
10. FE right panel과 suspect card, central character state 변화 확인
11. 최종 지목 payload 제출 후 verdict 확인
12. session payload/SSE/console log에 secret leakage 없는지 확인

## 8. 다음 실행 순서

1. BE dogfood용 E2E script 작성: session 생성 -> dialogue -> SSE once/replay -> contradiction -> accusation.
2. FE dogfood용 Playwright 또는 browser QA 작성: target 첫 화면 시각 체크 + BE-backed interaction.
3. BE EventProcessor/turnInterpreter의 빠진 케이스를 테스트로 먼저 고정.
4. FE right-column contradiction panel과 SSE reducer 차이를 보강.
5. case_001 단서 경로를 “플레이 가능한 사건” 기준으로 보강.
6. Docker refresh 후 실제 통합 smoke를 통과한 단위만 atomic commit 대상으로 묶는다.

## 9. 바로 잡아야 할 방향성

하지 말 것:

- FE에서 local truth로 모순/해금/범인을 계산하기
- AI prompt에 private solution을 넣고 guard로 막으려 하기
- 질문 추천 버튼을 메인 플레이로 만들기
- 테스트만 통과하고 Docker/browser dogfood 없이 commit-ready라고 보고하기
- mock fallback이 작동했다는 이유로 production flow가 된 것처럼 말하기

해야 할 것:

- BE state authority 유지
- AI는 공개 지식 기반의 자연스러운 연기와 proposedEvents만 담당
- FE는 noir investigation desk로 BE state 변화를 즉시 시각화
- SSE를 “장식”이 아니라 수사 상태 변화의 핵심 경로로 취급
- dogfood에서 실제로 사건을 한 번 플레이해보고 막히는 지점을 고친다
