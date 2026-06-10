# case_001 Agent 튜닝 프로토콜 — 스토리 개정안 기반

> 목적: `Docs/case_001_story_revision.md`의 개정된 사건 구조를 BE/AI 런타임 대화 품질까지 연결한다. 룰 기반 문장 치환이나 프롬프트 누적 땜질이 아니라, 데이터셋 → 지식 검색 → Agent 계약 → BE 이벤트 검증 → 테스트/프로브의 루프로 튜닝한다.

---

## 0. 원칙

1. BE가 권위다.
   - unlock, contradiction, pressure, final accusation, event 적용 여부는 BE RuleEngine/EventProcessor가 결정한다.
   - AI/GameMaster는 `proposedEvents`만 낸다.

2. 데이터 우선이다.
   - 캐릭터성/말투/비밀 단계/레드헤링은 case JSON, personaVariants, playerParaphrases, public evidence/relation context에 반영한다.
   - LLM prompt에는 데이터의 사용법과 계약을 넣고, 사건 사실 자체를 무한 반복 삽입하지 않는다.

3. validator는 불변식만 지킨다.
   - private leak, unsupported event, invalid refs, budget/unlock authority를 막는다.
   - 어색한 대사를 사후 문자열 치환으로 고치지 않는다.

4. 테스트는 route green이 아니라 transcript green이어야 한다.
   - matchedQuestionId, event, unlock뿐 아니라 실제 답변이 질문에 anchor되고 캐릭터별 diction/pressure 반응이 달라야 한다.

---

## 1. 이벤트 변경 이해

현재 dialogue graph는 다음 6개 Agent/노드 축으로 동작한다.

1. `KnowledgeRetriever`
   - 입력: case/session/player question/allowed refs.
   - 출력: Character용 public context + GameMaster용 event context.
   - 점검 포인트: 새 증거(`ev_pancreatic_diagnosis`, `ev_narcotic_supply_record`, `ev_childhood_photo`, `ev_choiyuna_ring_receipt`)가 matched evidence/contradiction 후보로 검색되는지.

2. `CharacterReactionJudgeAgent`
   - 입력: player raw utterance + public/retrieved context.
   - 출력 route: `answer_relevant`, `react_to_valid_pressure`, `challenge_player_contradiction`, `reject_false_premise`, `deflect_irrelevant`, `ask_clarification`, `refuse_meta_or_private`.
   - 점검 포인트: “CCTV 실루엣 + 한서연 사진첩”, “반지 영수증”, “불법 약품 기록” 같은 개정안 표현이 generic fallback으로 빠지지 않아야 한다.

3. `DialogueDirectorAgent`
   - 입력: reaction route + allowed statement/evidence.
   - 출력: function-transition plan (`name`, `arguments`, `transferTo`, `reason`).
   - 점검 포인트: route별 response contract가 캐릭터가 수행할 small move만 정의하고 정답/비밀을 열지 않아야 한다.

4. `CharacterAgent`
   - 입력: director plan + persona + public knowledge.
   - 출력: 캐릭터 대사 draft.
   - 점검 포인트: 캐릭터별 말투/방어 양식이 다르고, player utterance를 직접 받으며, pressure state별 sample/voice를 사용해야 한다.

5. `LightRuleCheck` / `GroundingCheckAgent`
   - 입력: draft + allowed refs + forbidden refs.
   - 출력: public-safe final candidate.
   - 점검 포인트: private truth leak와 fact drift만 막고, 자연스러움 개선을 deterministic replacement로 처리하지 않는다.

6. `GameMasterAgent`
   - 입력: checked reply + allowedEventPolicy + event_context.
   - 출력: `proposedEvents`.
   - 점검 포인트: proposed event는 BE가 허용한 turn policy 안의 public refs만 포함해야 한다.

BE `EventProcessor` 적용 규칙:

- `NOTE_FACT_ADDED`: source가 allowedEventPolicy의 related refs 안에 있어야 함.
- `NOTE_CONTRADICTION_CANDIDATE_ADDED`: contradictionId가 relatedContradictionIds 안에 있고, required statement/evidence가 visible이어야 함.
- `EVIDENCE_UNLOCKED`: AI가 임의로 열 수 없고, session.newlyUnlockedIds에 있는 evidence만 이벤트화됨.
- `TENSION_CHANGED`: AI-owned tension은 거부. RuleEngine validated contradiction 이후 deterministic event로만 발생.
- `VISUAL_STATE_CHANGED`: BE가 pressure 기반으로 생성.

---

## 2. 데이터셋 점검 항목

### 한서연

- 핵심 경로:
  - `con_room_claim_vs_entry_log`
  - `con_watch_time_manipulated`
  - `con_inheritance_motive`
- 필요 데이터:
  - 방 알리바이, 카드키 입장, 정전 카드키 중단, 회중시계 투척/시간 조작, 찢어진 유언장 동기.
- 캐릭터성:
  - 반말, 짧은 방어, 압박 시 말이 끊김.
  - 정전/시계/상속을 모두 인정하더라도 최종 범행 자백은 BE accusation 전까지 제한.

### 최윤아

- 레드헤링 경로:
  - `q_choiyuna_ring` → `ev_ring_near_victim`
  - `con_ring_vs_no_entry` → `ev_choiyuna_ring_receipt`, `q_choiyuna_affair`
  - `con_choiyuna_ring_vs_denial` → `ev_torn_will`, `rel_choiyuna_affair`
- 필요 데이터:
  - 반지, 반지 영수증, 내연 관계, 찢어진 유언장 가방 보관.
- 캐릭터성:
  - 업무적 존댓말, 일정/기록 뒤에 숨음, 사적 관계 질문에서 균열.

### 박민규

- 레드헤링 경로:
  - `q_parkmingyu_diagnosis` → `ev_pancreatic_diagnosis`, `ev_narcotic_supply_record`
  - `con_park_illegal_opioids`
- 필요 데이터:
  - 췌장암 4기, 여명 6개월, 펜타닐/모르핀 한도 초과, 면허 리스크.
- 캐릭터성:
  - 건조한 전문직 방어, 기록/처방/책임 어휘.

### 윤재호

- 은폐자/목격자 경로:
  - `q_yoonjaeho_hanseoyeon_bond` → `ev_childhood_photo`, `rel_yoonjaeho_hanseoyeon`
  - `con_yoon_witness_guilt` requires `ev_deleted_cctv`, `ev_childhood_photo`
  - unlock `st_yoonjaeho_witness`
- 필요 데이터:
  - 한서연을 8살부터 돌본 유대, 22:07~22:08 목격, 발견 시각 지연.
- 캐릭터성:
  - 공손하되 침묵이 길고, 한서연 언급 때 말끝이 짧아짐.

---

## 3. 테스트 재설계

### A. 정적 계약 테스트

- 전체 evidence count: 26.
- 초기 공개 evidence: 6.
- `ev_torn_will`은 최윤아 경로 뒤에만 공개.
- `q_yoonjaeho_will`은 유언장을 직접 unlock하지 않음.
- 신규 evidence 모두 reveal path + use/support path 보유.

### B. 예산-aware 메인 solution path

목표: 12문항 내 clear 가능성을 확인하되 모든 side route를 한 세션에 우겨 넣지 않는다.

권장 happy path:

1. 최윤아 반지 질문.
2. 최윤아 반지 현장 모순.
3. 최윤아 반지 영수증 모순 → 찢어진 유언장 unlock.
4. 한서연 카드키 입장 모순.
5. 한서연 after-pressure 질문.
6. 한서연 정전/회중시계 모순.
7. 한서연 상속/유언장 모순.
8. 최종 고발.

### C. side route probes

별도 세션에서 검증:

- 박민규: 병명/불법 약품 → illegal opioids contradiction.
- 윤재호: 정전/시계로 CCTV unlock → 사진첩 → witness guilt contradiction.
- 최윤아: affair/ring/will red herring closure.

### D. transcript quality probes

각 suspect별로 다음을 출력/검증:

- turn number
- player utterance
- matchedQuestionId
- dialogueMode / reactionRoute
- retrieved matched evidence/statements/timeline
- proposedEvents
- appliedEvents
- answer preview/full line
- pressure/tension state
- remainingQuestions

품질 assertion:

- raw ID/비공개 해설/시스템 문구 없음.
- 같은 suspect의 high-pressure 답변 exact repeat 없음.
- final breakdown은 unlock된 전용 question으로만 매칭.
- non-culprit resigned는 자기 비밀만 인정하고 범인 진실을 누설하지 않음.
- answer가 player utterance의 구체 질문을 회피하지 않음.

---

## 4. 6개 Agent 보강 방향

### KnowledgeRetriever

- 목표: 개정안의 새 증거/관계/모순이 retrieved context에 들어오는지 확인.
- 보강 방식:
  - case data의 `playerParaphrases`, evidence description, relation conflict 문장을 풍부하게 한다.
  - 검색 테스트를 먼저 추가한다.
- 금지:
  - 특정 질문 문자열만 hardcode해서 우회 매칭.

### CharacterReactionJudgeAgent

- 목표: player claim이 public context와 어떤 관계인지 route로 판정.
- 보강 방식:
  - prompt/decision schema에 `matchedEvidence`, `candidateContradictionIds`, `playerClaimAssessment`를 명시적으로 비교하게 한다.
  - route decision probe를 추가한다.
- 금지:
  - “CCTV면 무조건 valid pressure” 같은 one-off branch.

### DialogueDirectorAgent

- 목표: route별 function-transition contract를 명확히 하되, 사건 내용을 중복 삽입하지 않는다.
- 보강 방식:
  - `functionCall.arguments`에 playerMessage, focusTerms, admissionLevel, stateIntent를 유지.
  - route-specific allowed admission을 개정안에 맞게 조정.

### CharacterAgent

- 목표: 캐릭터별 diction/방어 방식/압박 반응을 자연스럽게 생성.
- 보강 방식:
  - `personaVariants`와 sampleLines를 pressure stage별로 확장.
  - active persona overlay와 retrieved context를 prompt section으로 구조화.
  - 동일 stage에서 sample pool 부족으로 반복되는 문제를 데이터로 해결.
- 금지:
  - 사후 `replace()`로 존댓말/반말을 대량 보정.

### LightRuleCheck / GroundingCheckAgent

- 목표: public-safe, grounded, private-leak free.
- 보강 방식:
  - raw player question anchoring 유지 여부 점검.
  - repaired/blocked reason이 transcript에 남게 한다.
- 금지:
  - 어색한 캐릭터 대사를 validator가 새로 써서 해결.

### GameMasterAgent

- 목표: event proposal은 public refs와 turn policy에 맞게 작게 제안.
- 보강 방식:
  - event_context에 candidate contradiction/evidence/statement refs가 들어오는지 테스트.
  - BE rejected event reason을 통계화해 prompt/data 문제를 찾는다.
- 금지:
  - AI가 tension/evidence unlock/final verdict를 직접 결정.

---

## 5. 반복 루프

1. 현재 failing transcript/probe를 실행한다.
2. 실패를 route / retrieval / persona / event / rule authority 중 하나로 분류한다.
3. 테스트를 먼저 바꾼다.
4. 데이터셋 또는 Agent contract를 최소 단위로 보강한다.
5. targeted test + transcript probe를 실행한다.
6. 전체 BE test를 실행한다.
7. Docker BE refresh 후 API/SSE smoke를 실행한다.

---

## 6. 현재 관찰된 후속 작업

- 기존 full-suite 실패 중 일부는 개정 전 expectation이다.
  - 최종 고발은 이제 `ev_storm_blackout`, `ev_broken_watch`, `con_watch_time_manipulated`까지 필요하다.
  - 상속 모순만으로 accusation readiness가 true이면 안 된다.
- pressure collapse 시나리오는 최윤아 반지/유언장 재배선과 윤재호 목격자 경로를 반영해 다시 작성해야 한다.
- event count 기반 assertion은 brittle하다. 대신 event type + payload contract + BE 적용 여부를 검증한다.
- matchedRefs는 단일 evidence만 기대하지 말고, 개정안에서 실제로 같이 연결되는 visible context 묶음을 검증한다.
