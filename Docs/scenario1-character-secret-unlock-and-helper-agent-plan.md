# Scenario1 character secret unlock + HelperAgent routing plan

## 판단
현재 deterministic seed는 품질 게이트를 통과하기 위한 안전 fallback에 가깝고, 최종 플레이 경험으로는 부족하다. 특히 다음 문제가 있다.

- 캐릭터별 말투/관계/방어기제가 약해서 모두 비슷한 안내문처럼 들린다.
- 증거/관계가 대화 속에서 자연스럽게 해금되기보다 route 결과로만 보인다.
- 압박 단계가 올라갔을 때만 가능한 질문/관계 추궁/증거 추궁의 감각이 부족하다.
- 모든 캐릭터가 “체념 단계”까지 갈 수 있는지, 그때 무엇을 드러내는지의 작가용 해결선이 명시되어 있지 않다.
- 사용자가 맥락을 잃었을 때 도와줄 GameMaster/HelperAgent가 아직 없다.

따라서 다음 개혁은 “seed 문장 다듬기”가 아니라, 캐릭터별 비밀 사다리와 pressure-gated unlock 구조를 먼저 확정하고 그 위에 CharacterAgent 대사와 HelperAgent 힌트를 얹는 방식으로 진행한다.

## 핵심 게임 루프
1. 플레이어가 자연어로 캐릭터에게 질문한다.
2. CharacterReactionJudgeAgent가 route를 고른다.
3. CharacterAgent는 해당 캐릭터의 persona, relation, pressure stage, 공개 evidence를 바탕으로 대답한다.
4. 대답/압박/모순 성공이 특정 secret rung을 해금한다.
5. 해금된 secret rung은 새 질문, 증거, 관계 edge, helper hint 후보를 연다.
6. 사용자가 충분한 공개 정보를 모으면 최종 고발로 승리/패배를 확정한다.

## pressure stage 정의
각 캐릭터는 최소 4단계까지 진행 가능해야 한다.

| stage | pressure | 상태 | 대사 목표 | 해금 성격 |
| --- | ---: | --- | --- | --- |
| guarded | 0-19 | 경계 | 공개 알리바이/표면 관계만 말함 | 기본 질문 |
| defensive | 20-49 | 방어 | 불편한 증거를 회피하거나 상대를 탓함 | 관계 단서, 소문 |
| shaken | 50-79 | 동요 | 비밀의 일부를 인정하지만 핵심 책임은 부정 | 새 증거/타임라인 |
| resigned | 80-100 | 체념 | 자기 비밀은 인정. 단, 진범이 아니면 진범 단정은 피함 | 마지막 진술/관계 고백 |

중요: 모든 캐릭터가 resigned까지 진입 가능해야 한다. 단, resigned가 곧 범인 고백은 아니다. 비범인 캐릭터는 자기 비밀/거짓말의 이유를 털어놓고, 진범인 한서연만 사건 핵심 구조와 연결된다.

## 캐릭터별 secret ladder

### 한서연 — 진범 / 상속과 서재 접근
- guarded
  - 표면: “방에 있었다.”
  - 허용 질문: 알리바이, 상속, 서재 접근 여부.
- defensive
  - trigger: 서재 출입 기록 또는 방 진술 모순.
  - 대사 방향: 질문자를 밀어내고 가족 갈등을 축소한다.
  - unlock: q_hanseoyeon_after_pressure, con_room_claim_vs_entry_log.
- shaken
  - trigger: 찢어진 유언장 + 상속 부정 진술 모순.
  - 대사 방향: “아버지가 나를 버리려 했다”는 감정을 드러내지만 살해는 부정.
  - unlock: ev_torn_will, con_inheritance_motive.
- resigned
  - trigger: 반지/출입기록/유언장/정전 조작 라인 결합.
  - 대사 방향: 체념, 분노, 가족 내 버림받음. 최종 고발 직전의 정서적 폭발.
  - unlock: final accusation readiness.

### 윤재호 — 집사 / 충성심과 침묵
- guarded
  - 표면: “시신 발견자, 오랜 집사.”
- defensive
  - trigger: 순찰 기록, 유언장 변경 사실 질문.
  - 대사 방향: 집안을 지키려는 말투. 가족 문제를 외부인에게 말하기 싫어함.
  - unlock: rel_yoonjaeho_loyalty.
- shaken
  - trigger: 유언장/복도 기록/한서연과의 관계 edge.
  - 대사 방향: “알고도 말하지 않았다”는 죄책감.
  - unlock: 한서연 동기 라인을 강화하는 relation clue.
- resigned
  - trigger: 한서연 압박 이후 윤재호 재질문.
  - 대사 방향: 진범 고발은 아니지만 “그 아이가 무너지는 걸 봤다”는 증언.
  - unlock: final narrative corroboration.

### 박민규 — 주치의 / 약과 직업적 은폐
- guarded
  - 표면: 약 복용 기록 이상 없음.
- defensive
  - trigger: 약 상자, 처방 기록 질문.
  - 대사 방향: 전문 용어와 권위로 방어.
  - unlock: q_parkmingyu_medicine.
- shaken
  - trigger: 피해자의 건강 상태와 사망 방식이 약물살해가 아님을 대조.
  - 대사 방향: 자기 과실/처방 은폐를 인정하지만 살해와는 분리.
  - unlock: red herring 정리, 범인 후보 축소 힌트.
- resigned
  - trigger: 약 관련 의심이 해소되고 한서연 라인 증거가 충분할 때.
  - 대사 방향: “내가 숨긴 건 죽음의 원인이 아니라 내 평판이었다.”
  - unlock: helper가 “약은 동기는 만들지만 결정타는 아니다” 힌트 가능.

### 최윤아 — 연인/와인잔 / 관계 은폐
- guarded
  - 표면: 와인을 마시지 않았다, 피해자와 선을 긋는다.
- defensive
  - trigger: 와인잔 립스틱, 피해자와의 관계 질문.
  - 대사 방향: 가십으로 몰아가지 말라며 날카롭게 반응.
  - unlock: q_choiyuna_wine.
- shaken
  - trigger: 와인잔 + 관계 edge + 피해자 시간대 대조.
  - 대사 방향: 관계는 인정하되 살해 시간/현장 접근과 분리.
  - unlock: rel_choiyuna_affair 또는 equivalent relation clue.
- resigned
  - trigger: 한서연 압박 이후 최윤아 재질문.
  - 대사 방향: 피해자에 대한 감정과 비밀 관계를 인정. 진범은 아니지만 동기 혼선을 해소.
  - unlock: red herring closure.

## 질문/해금 게이트

### evidence question gate
- guarded: 기본 공개 증거만 질문 가능.
- defensive 이상: 해당 캐릭터와 직접 연결된 증거 질문이 더 강한 route로 처리됨.
- shaken 이상: 피해자와의 관계, 숨긴 동기, 알리바이 균열 질문이 새 진술을 연다.
- resigned: 최종 정리형 질문과 고백형 진술이 열린다.

### relation question gate
- 관계 edge가 locked이면 직접적인 관계 추궁은 deflect/ask_clarification으로 처리하되 HelperAgent가 “먼저 관련 증거를 확인하라”고 안내할 수 있다.
- relation edge가 candidate이면 캐릭터는 부정/회피하면서 pressure를 올린다.
- relation edge가 unlocked이면 캐릭터는 관계를 인정하거나 의미를 재해석한다.

## HelperAgent(Routing) 설계

### 목적
사용자가 맥락을 못 찾을 때 세계관 밖 정답을 주지 않고, 탐정 조수처럼 다음 행동을 제안한다.

### trigger
- 2턴 이상 unmatched/irrelevant/ask_clarification 반복.
- 같은 캐릭터에게 동일한 route 반복.
- remainingQuestions가 줄어드는데 새 증거/모순/관계 해금이 없음.
- accusation readiness가 낮은데 최종 고발 drawer를 여는 경우.
- contradiction candidate는 있으나 제출 가능한 evidence/statement pair를 고르지 못하는 경우.

### output contract
```json
{
  "helperRoute": "nudge_evidence|nudge_relation|nudge_contradiction|nudge_switch_suspect|nudge_accusation_ready|silent",
  "confidence": 0.0,
  "tone": "noir_assistant",
  "message": "정답이 아니라 다음 조사 방향을 암시하는 1-2문장",
  "suggestedActions": [
    {"type": "ask_suspect|open_evidence|open_relations|try_contradiction", "targetId": "public id", "label": "UI label"}
  ],
  "publicRefs": {"evidenceIds": [], "statementIds": [], "relationIds": [], "suspectIds": []}
}
```

### route examples
- nudge_evidence: “서재 출입 기록은 아직 말과 맞물리지 않았습니다. 한서연에게 시간대를 다시 좁혀 물어보세요.”
- nudge_relation: “관계도에 새 선이 생겼습니다. 유언장보다 먼저, 그 침묵이 누구를 보호했는지 확인해보는 게 좋겠습니다.”
- nudge_contradiction: “지금은 질문보다 대조가 필요합니다. ‘방에 있었다’는 말과 22:02 출입 기록을 같은 탁자 위에 올려보세요.”
- nudge_switch_suspect: “약 이야기는 연기가 많지만 불꽃은 아닐 수 있습니다. 다른 인물의 알리바이 균열을 확인하세요.”
- nudge_accusation_ready: “고발은 빠릅니다. 범인 이름보다 먼저, 왜 거짓말을 해야 했는지와 현장 접촉 근거를 묶어야 합니다.”

## Helper UI
- InterrogationStage 하단 또는 우측에 “조수의 메모” 카드로 표시.
- 기본은 접힌 상태 또는 subtle badge.
- 같은 힌트를 반복하지 않고, 사용자가 클릭하면 관련 drawer/evidence/relation으로 이동.
- 정답/비공개/진범 여부는 노출 금지.
- 실패 UI에서는 “어디서 잘못 짚었는지”를 HelperAgent 요약으로 보여줄 수 있다.

## 구현 순서
1. Docs/case schema에 `secretLadders`, `pressureGates`, `helperHintRules` 추가.
2. BE read model에 public-safe `helperSuggestion` 추가.
3. `GameMasterHelperAgent` 또는 `HelperAgent` 추가: LLM-first JSON + deterministic fallback.
4. route graph의 post-processing node로 helper routing 추가. state mutation 없음.
5. FE `HelperAgentCard` 추가.
6. game-feel probe에 “막힌 사용자 3턴 → helper nudge” 시나리오 추가.
7. seed fallback은 캐릭터별 persona templates로 교체. 안전 seed는 최후 fallback로만 유지.

## acceptance checks
- 모든 캐릭터가 pressure 80+에서 resigned visual/emotional state로 들어갈 수 있다.
- 비범인 캐릭터 resigned는 자기 비밀을 고백하지만 진범 정보를 직접 누설하지 않는다.
- 각 캐릭터별로 최소 1개 relation unlock, 1개 evidence/statement unlock 또는 red-herring closure가 있다.
- HelperAgent는 막힌 상황에서만 표시되고, 정답 대신 다음 행동을 제안한다.
- 최종 고발 성공/실패 UI는 result persisted session load에서도 표시된다.
