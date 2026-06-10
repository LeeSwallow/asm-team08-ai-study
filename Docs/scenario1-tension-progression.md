# Scenario 1 Tension Progression

Owner: DOCS / BE / AI
Scope: case_001 player-facing tension scenario, clue path, emotional pressure flow, and demo interrogation order.
Runtime source of truth: `BE/data/cases/case_001.json`
Last aligned with branch: `qa/agent-performance-improvement`

## 1. One-line pitch

정전은 숨겨진 반전이 아니라 처음부터 보이는 불길한 기회 단서다. 플레이어는 22:05~22:07의 정전, CCTV 공백, 깨진 회중시계의 물리 흔적을 같은 시간축에 놓고, 한서연의 방 알리바이와 상속 동기가 무너진 뒤에야 “정전 중 현장 조작”이라는 결론에 도달한다.

## 2. Core design boundary

### Public from session start

The following are public opportunity context. They may appear in evidence/timeline panels and can be discussed by characters without spoiling the culprit.

- `ev_storm_blackout`
  - name: 정전 기록
  - time: 22:05~22:07
  - meaning: 저택 2층 일부 정전과 CCTV 중단이 있었다.
- `tl_blackout`
  - title: 저택 2층 정전
  - time: 22:05~22:07
  - source: `ev_storm_blackout`
- `ev_broken_watch`
  - name: 깨진 회중시계
  - meaning: 멈춘 시각과 파편 방향이 자연스럽지 않다.

### Hidden until proven

The following must not be stated as truth before the player connects the public facts.

- 정전 중 누가 현장을 조작했는가.
- 한서연이 범인이라는 결론.
- 회중시계가 조작됐다는 확정 진술.
- `ev_deleted_cctv`의 decisive meaning before unlock.
- solution/method/private motive text.

AI/Helper wording rule:
- Allowed: “정전 시간과 멈춘 시계의 물리 흔적을 같은 시간축에 놓아 보라.”
- Not allowed before proof: “한서연이 정전 중 시계를 조작했다.”

## 3. Four-act objective progression

### Act 1 — alibi_collection

Current objective:

> 먼저 서재 출입 기록과 시간대가 맞지 않는 알리바이를 찾고, 수상한 비밀과 핵심 거짓말을 구분하라.

Player-visible setup:

- death window: 22:00~22:10
- 한서연 statement: “22:00에 제 방에 있었어요.”
- `ev_study_entry_log`: 22:02 한서연 카드키 서재 출입 기록
- `ev_storm_blackout` / `tl_blackout`: 22:05~22:07 정전
- `ev_broken_watch`: 깨진 회중시계
- `ev_window_bolt`: 창문 안쪽 잠금

Primary contradiction:

- `con_room_claim_vs_entry_log`
- title: 방에 있었다는 진술과 서재 출입 기록의 충돌
- evidence: `ev_study_entry_log`
- statement: `st_hanseoyeon_room_2200`
- pressureDelta: 40

Narrative effect:

한서연의 첫 방어선이 깨진다. 이 단계에서는 범행을 고백하지 않는다. “방에 있었다”가 “잠깐 들어갔을 뿐”으로 후퇴한다.

### Act 2 — motive_reveal

Current objective:

> 첫 거짓말 이후 열린 단서로 상속 갈등과 현장 접촉 흔적을 분리해 검토하라.

Primary contradiction:

- `con_inheritance_motive`
- title: 상속 갈등과 찢어진 유언장
- evidence: `ev_torn_will`
- statement: `st_hanseoyeon_no_reason`
- pressureDelta: 35

Narrative effect:

단순 알리바이 거짓말이 감정적 동기로 확장된다. 한서연은 “죽일 이유는 없었다”고 버티지만, 찢어진 유언장이 상속 축소와 분노를 드러낸다.

Emotional state:

- defensive -> shaken
- cold denial -> anger / abandonment wound
- still no full confession

### Act 3 — scene_manipulation_review

Current objective:

> 정전 기록, CCTV 공백, 깨진 회중시계의 시간축을 묶어 현장 조작 가능성을 검토하라.

Dedicated clue path:

- `path_blackout_scene_manipulation`
- title: 정전과 현장 조작
- resolves: `con_watch_time_manipulated`
- unlocks: `ev_deleted_cctv`

Steps:

1. `tl_blackout`
   - type: timeline
   - prompt: 22:05~22:07 정전이 사망 추정 시간 안에 들어오는지 확인한다.
2. `ev_storm_blackout`
   - type: evidence
   - prompt: 관리실 로그와 CCTV 중단이 같은 시간대인지 확인한다.
3. `ev_broken_watch`
   - type: evidence
   - prompt: 회중시계가 멈춘 시각과 파편 방향이 자연스러운지 대조한다.
4. `ev_deleted_cctv`
   - type: evidence
   - prompt: 정전 이후 드러난 CCTV 공백이 현장 조작 시간을 보강하는지 확인한다.

Primary contradiction:

- `con_watch_time_manipulated`
- title: 회중시계 시각 조작 의혹
- evidence:
  - `ev_broken_watch`
  - `ev_storm_blackout`
- statement:
  - `st_hanseoyeon_pressure`
- pressureDelta: 25
- message: 정전 시간과 부자연스러운 회중시계 파편은 현장 조작 가능성을 뒷받침합니다.

Narrative effect:

정전은 “범인이 누구인지”를 말하지 않는다. 대신 범인이 현장 시간을 조작할 수 있었던 창을 만든다. 회중시계의 물리 흔적과 결합될 때, 단순 정전이 현장 조작 의혹으로 바뀐다.

Emotional state:

- shaken -> critical
- answer pattern shifts from denial to fragmented evasion
- 한서연 can no longer return to “방에 있었다”

### Act 4 — final_accusation

Current objective:

> 범인, 동기, 수단, 알리바이 모순 근거를 모아 최종 지목하라.

Entry condition:

- `con_watch_time_manipulated` discovered

Required final reasoning bundle:

- 알리바이 collapse:
  - `st_hanseoyeon_room_2200`
  - `ev_study_entry_log`
  - `con_room_claim_vs_entry_log`
- motive collapse:
  - `st_hanseoyeon_no_reason`
  - `ev_torn_will`
  - `con_inheritance_motive`
- opportunity / manipulation:
  - `tl_blackout`
  - `ev_storm_blackout`
  - `ev_broken_watch`
  - `ev_deleted_cctv`
  - `con_watch_time_manipulated`
- optional physical contact reinforcement:
  - `ev_ring_near_victim`
  - `con_ring_vs_no_entry`

Narrative effect:

The final accusation should feel earned because the player has already proven:

1. 한서연 lied about location.
2. 한서연 had a motive.
3. The blackout created an opportunity for scene manipulation.
4. The broken watch and CCTV gap make the manipulation plausible.

## 4. Emotional pressure arc for 한서연

### guarded

Surface line:

- “22:00에는 제 방에 있었어요.”

Player pressure:

- Ask alibi.
- Compare time window.

Character texture:

- controlled
- cold
- dismissive

### defensive

Trigger:

- `con_room_claim_vs_entry_log`

Surface line:

- “잠깐 들어갔을 뿐이에요. 그때 이미 상황이 이상했습니다.”

Character texture:

- sharp
- attacks the premise
- refuses to explain fully

### shaken

Trigger:

- `con_inheritance_motive`

Surface line:

- “상속 문제로 다툰 적은 있지만 죽일 이유는 없었어요.”

Character texture:

- anger leaks through
- abandonment wound appears
- motive is emotionally visible but still denied

### critical / resigned

Trigger:

- `con_watch_time_manipulated`
- repeated pressure around blackout, watch, will, and study access

Expected markers:

- “무서웠”
- “거짓말”
- “회장님”
- “내가”

Character texture:

- fragmented speech
- no longer controls the room
- admits hidden fear/lie, while final verdict remains BE-authoritative

## 5. Demo interrogation sequence

Use this sequence for a presentation because it shows the tension escalation clearly without requiring the player to discover every side clue.

1. 한서연
   - “22:00에 어디 있었나요?”
   - Purpose: establish room alibi.

2. 한서연
   - “22시에 방에 있었다는 말은 서재 출입 기록과 모순입니다.”
   - Purpose: trigger first contradiction and pressure spike.

3. 한서연
   - “그게 답이라고? 카드키 기록이 있는데 계속 회피하지 마.”
   - Purpose: keep pressure from resolving too quickly.

4. 한서연
   - “서재에 들어갔다면 무엇을 봤나요?”
   - Purpose: force retreat from total denial to partial presence.

5. 윤재호
   - “정전 당시 무엇을 했나요?”
   - Purpose: bring blackout into the social/timeline layer without making it a culprit reveal.

6. 한서연
   - “정전 기록과 부자연스러운 회중시계 파편은 현장 조작 가능성을 보여줍니다.”
   - Purpose: connect blackout opportunity with watch manipulation.

7. 한서연
   - “그 시계랑 정전 이야기를 피하지 마. 네 말이 납득 안 돼.”
   - Purpose: pressure follow-up; prevent abrupt collapse.

8. 한서연
   - “상속 문제로 다툰 적 있나요?”
   - Purpose: move from opportunity to motive.

9. 한서연
   - “죽일 이유가 없다는 말은 찢어진 유언장과 모순입니다.”
   - Purpose: expose motive contradiction.

10. 한서연
    - “유언장까지 나왔는데 아직 죽일 이유가 없다는 게 말이 된다고 생각해?”
    - Purpose: emotional escalation.

11. 한서연
    - “이제 버티지 말고, 서재에서 정말 숨긴 걸 말해.”
    - Purpose: trigger breakdown / resigned stage.

## 6. Presentation explanation script

Short version:

> 이 사건에서 정전은 반전 카드가 아니라, 처음부터 공개되는 불길한 시간축 단서입니다. 플레이어는 먼저 한서연의 방 알리바이를 서재 출입 기록으로 깨고, 이후 유언장으로 동기를 확인합니다. 그 다음 22:05~22:07 정전, CCTV 공백, 깨진 회중시계를 같은 시간축에 놓으면서 현장 조작 가능성을 입증합니다. 그래서 최종 붕괴는 갑작스러운 고백이 아니라, 알리바이·동기·기회·조작 증거가 차례로 쌓인 결과가 됩니다.

Long version:

> 플레이어는 처음부터 정전 기록을 볼 수 있습니다. 하지만 정전 자체는 범인을 말해주지 않습니다. 정전은 단지 ‘그 시간대에 무언가를 숨길 수 있었다’는 기회 조건입니다. 이 기회 조건이 깨진 회중시계, CCTV 공백, 한서연의 서재 출입 기록과 결합될 때 비로소 현장 조작이라는 추론이 됩니다. 그래서 AI 캐릭터도 처음부터 범인을 암시하지 않고, BE가 공개한 증거와 모순 단계에 맞춰 반응합니다.

## 7. Implementation anchors

Runtime data:

- `BE/data/cases/case_001.json`

Primary tests:

- `BE/tests/test_case_001_blackout_story_integrity.py`
- `BE/tests/test_scenario1_pressure_collapse_scenarios.py`
- `BE/tests/test_api_smoke.py::test_storyline_public_payload_and_objective_progression`
- `BE/tests/test_api_smoke.py::test_case_001_progression_can_unlock_all_suspects_relations_and_evidence_within_limit`

Related docs:

- `Docs/story-data-contract.md`
- `Docs/story-agent-contract.md`
- `Docs/scenario1-character-secret-unlock-and-helper-agent-plan.md`

## 8. Guardrails

Do not regress these rules:

1. `ev_storm_blackout` must remain visible from session start.
2. `tl_blackout` must remain in `visibleTimeline` and `caseFile.visibleTimeline`.
3. Scene manipulation must not be publicly asserted before the relevant contradiction/evidence path is surfaced.
4. Helper hints may suggest comparing blackout time and watch physics, but must not name the culprit.
5. Final accusation should come after `con_watch_time_manipulated`, not immediately after the motive contradiction.
