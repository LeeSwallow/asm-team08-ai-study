# Case 001: 진실은, 서로의 말 속에 있다

## 1. Scenario

| 항목 | 내용 |
| --- | --- |
| Scene ID | `scene_001` |
| 제목 | 진실은, 서로의 말 속에 있다 |
| 한 줄 소개 | 폭풍우 치던 밤, 서재에서 사망한 피해자의 죽음을 두고 네 명의 용의자가 서로 다른 알리바이를 주장한다. |
| 피해자 | `victim_kangdojun` 강도준 |
| 사건 발생 장소 | 저택 2층 서재 |
| 사건 발생 추정 시각 | 22:00~22:10 |
| 질문 제한 | 12회 |
| 플레이어 목표 | 용의자들의 진술과 증거를 교차검증해 범인, 동기, 수단, 핵심 모순을 밝혀낸다. |

## 2. Opening Information

| 정보 | 공개 내용 |
| --- | --- |
| 사건 개요 | 강도준은 22:10경 서재에서 쓰러진 채 발견됐다. 외부 침입 흔적은 없다. |
| 최초 발견자 | `char_yoonjaeho` 윤재호 |
| 초기 증거 | 깨진 회중시계, 와인잔, 서재 출입 기록 |
| 초기 용의자 | 한서연, 윤재호, 박민규, 최윤아 |

## 3. Characters

| Character ID | 이름 | 역할 | 공개 프로필 | 숨기는 정보 | 범인 여부 |
| --- | --- | --- | --- | --- | --- |
| `char_hanseoyeon` | 한서연 | 조카 | 상속 문제로 피해자와 갈등이 있었다. | 22:02에 서재에 들어갔지만 피해자가 이미 쓰러져 있었다고 주장하려 한다. | Yes |
| `char_yoonjaeho` | 윤재호 | 집사 | 사건 최초 발견자. 저택 내부 사정을 잘 안다. | 피해자의 유언장 변경 사실을 알고 있었다. | No |
| `char_parkmingyu` | 박민규 | 주치의 | 피해자의 건강을 관리했다. | 피해자의 약 처방 변경 문제로 다툰 적이 있다. | No |
| `char_choiyuna` | 최윤아 | 비서 | 피해자의 일정과 업무를 관리했다. | 피해자가 비밀리에 만난 인물을 알고 있다. | No |

## 4. Victim Relationships

| Relationship ID | 인물 | 피해자와의 관계 | 갈등/동기 후보 | 공개 여부 |
| --- | --- | --- | --- | --- |
| `rel_hanseoyeon_inheritance` | 한서연 | 조카이자 상속 후보 | 상속 비율 변경으로 강한 갈등 | 시작 공개 |
| `rel_yoonjaeho_loyalty` | 윤재호 | 오래된 집사 | 유언장 변경 사실을 숨김 | 모순 해금 |
| `rel_parkmingyu_medical` | 박민규 | 주치의 | 처방 문제로 책임 추궁 가능성 | 시작 공개 |
| `rel_choiyuna_schedule` | 최윤아 | 비서 | 피해자의 비밀 일정 관리 | 질문 해금 |

## 5. Evidence

| Evidence ID | 이름 | 유형 | 설명 | 출처/발견 위치 | 관련 시간 | 신뢰도 | 공개 조건 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ev_broken_watch` | 깨진 회중시계 | physical | 21:40에 멈춰 있다. 유리 파편이 부자연스럽다. | 서재 바닥 | 21:40 | 0.65 | 시작 공개 |
| `ev_wine_glass` | 와인잔 | physical | 서재 책상에서 발견. 립스틱 흔적이 남아 있다. | 서재 책상 | 22:00 전후 | 0.80 | 시작 공개 |
| `ev_study_entry_log` | 서재 출입 기록 | record | 22:02에 한서연의 출입 기록이 남아 있다. | 저택 보안 시스템 | 22:02 | 0.95 | 시작 공개 |
| `ev_torn_will` | 찢어진 유언장 | physical | 상속 비율이 변경된 흔적이 있다. | 서재 금고 옆 | 불명 | 0.85 | 윤재호 심문 후 공개 |
| `ev_servant_log` | 부검 전 기록 | record | 사망 추정 시각은 22:00~22:10이다. | 현장 기록 | 22:00~22:10 | 0.90 | 시작 공개 |
| `ev_phone_call` | 통화 기록 | digital | 21:55에 피해자가 비서에게 전화를 걸었다. | 피해자 휴대폰 | 21:55 | 0.90 | 최윤아 질문 후 공개 |
| `ev_medicine_box` | 약 상자 | physical | 복용 시간이 21:30으로 표시되어 있다. | 침실 | 21:30 | 0.75 | 박민규 질문 후 공개 |
| `ev_storm_blackout` | 정전 기록 | record | 22:05~22:07 사이 저택 일부가 정전됐다. | 관리실 로그 | 22:05~22:07 | 0.88 | 윤재호 질문 후 공개 |

## 6. Character Timelines

### 6.1 Public Timeline

| 인물 | 시간 | 주장 위치 | 주장 내용 | Statement ID |
| --- | --- | --- | --- | --- |
| 한서연 | 22:00 | 자기 방 | "저는 그 시간에 제 방에 있었어요." | `st_hanseoyeon_room_2200` |
| 윤재호 | 22:10 | 2층 복도 | "순찰 중 서재 문이 열려 있는 걸 보고 발견했습니다." | `st_yoonjaeho_found_2210` |
| 박민규 | 22:00 | 손님방 | "피해자의 약 복용 상태를 확인한 뒤 방에 있었습니다." | `st_parkmingyu_guestroom_2200` |
| 최윤아 | 21:55 | 1층 응접실 | "피해자에게 전화를 받았지만 서재에는 가지 않았습니다." | `st_choiyuna_call_2155` |

### 6.2 Actual Timeline

| 인물 | 시간 | 실제 위치 | 실제 행동 | 근거 증거 |
| --- | --- | --- | --- | --- |
| 한서연 | 21:58 | 2층 복도 | 서재로 이동 | `ev_study_entry_log` |
| 한서연 | 22:02 | 서재 | 피해자와 상속 문제로 대면 | `ev_study_entry_log`, `ev_torn_will` |
| 한서연 | 22:05 | 서재 | 정전 중 현장을 조작 | `ev_storm_blackout`, `ev_broken_watch` |
| 윤재호 | 22:10 | 서재 앞 | 쓰러진 피해자를 발견 | `st_yoonjaeho_found_2210` |
| 박민규 | 22:00 | 손님방 | 약 상자 기록을 확인 | `ev_medicine_box` |
| 최윤아 | 21:55 | 1층 응접실 | 피해자와 통화 | `ev_phone_call` |

## 7. Statements

| Statement ID | 인물 | 질문 | 진술 | 관련 시간 | 관련 장소 | 해금 조건 |
| --- | --- | --- | --- | --- | --- | --- |
| `st_hanseoyeon_room_2200` | 한서연 | 그 시간에 어디 있었나요? | 저는 22:00에 제 방에 있었어요. | 22:00 | 자기 방 | 시작 공개 |
| `st_hanseoyeon_no_reason` | 한서연 | 상속 문제로 다툰 적 있나요? | 상속 문제로 다툰 적은 있지만 죽일 이유는 없었어요. | 불명 | 불명 | 시작 공개 |
| `st_yoonjaeho_found_2210` | 윤재호 | 피해자를 언제 발견했나요? | 22:10쯤 서재 문이 열려 있는 걸 봤습니다. | 22:10 | 서재 앞 | 시작 공개 |
| `st_parkmingyu_guestroom_2200` | 박민규 | 22:00에 어디 있었나요? | 손님방에서 의료 기록을 정리하고 있었습니다. | 22:00 | 손님방 | 시작 공개 |
| `st_choiyuna_call_2155` | 최윤아 | 피해자와 마지막으로 연락한 때는? | 21:55에 전화를 받았지만 직접 만나진 않았습니다. | 21:55 | 응접실 | 시작 공개 |
| `st_hanseoyeon_pressure` | 한서연 | 서재 출입 기록을 제시한다 | 잠깐 들어갔을 뿐이에요. 그때 이미 상황이 이상했습니다. | 22:02 | 서재 | `con_room_claim_vs_entry_log` |

## 8. Contradictions

| Contradiction ID | 제목 | 관련 인물 | 필요한 진술 | 필요한 증거 | 심각도 | 성공 시 결과 |
| --- | --- | --- | --- | --- | --- | --- |
| `con_room_claim_vs_entry_log` | 방에 있었다는 진술과 서재 출입 기록의 충돌 | 한서연 | `st_hanseoyeon_room_2200` | `ev_study_entry_log` | core | 한서연 압박 상승, `st_hanseoyeon_pressure` 해금 |
| `con_watch_time_manipulated` | 회중시계 시각 조작 의혹 | 한서연 | `st_hanseoyeon_pressure` | `ev_broken_watch`, `ev_storm_blackout` | major | 정전 중 현장 조작 가능성 공개 |
| `con_inheritance_motive` | 상속 갈등과 찢어진 유언장 | 한서연 | `st_hanseoyeon_no_reason` | `ev_torn_will` | core | 동기 확정 |
| `con_secret_call` | 피해자의 마지막 통화와 비서의 은폐 | 최윤아 | `st_choiyuna_call_2155` | `ev_phone_call` | minor | 피해자가 유언장 변경을 준비했음을 암시 |

## 9. Solution

| 항목 | 정답 |
| --- | --- |
| 범인 | 한서연 |
| 동기 | 상속 비율 변경으로 인한 갈등 |
| 수단 | 서재에서 피해자와 대면 후 정전 시간을 이용해 현장을 조작 |
| 결정적 모순 | 22:00에 방에 있었다는 진술과 22:02 서재 출입 기록의 충돌 |
| 필수 증거 | `ev_study_entry_log`, `ev_torn_will` |
| 필수 진술 | `st_hanseoyeon_room_2200`, `st_hanseoyeon_no_reason` |

## 10. Ending Feedback

| 결과 | 표시 내용 |
| --- | --- |
| 정답 | 한서연의 알리바이는 서재 출입 기록과 충돌했고, 찢어진 유언장이 동기를 뒷받침했다. |
| 범인은 맞지만 근거 부족 | 범인은 맞혔지만 상속 동기 또는 서재 출입 모순을 충분히 입증하지 못했다. |
| 오답 | 일부 증거가 의심을 만들었지만, 결정적 모순은 한서연의 알리바이에 있었다. |

## 11. Scenario1 Character Reaction Routes

Scenario1 심문은 feedback2 기준으로 현재 선택된 용의자가 플레이어 발화를 직접 판단하는 route 구조를 사용한다. Provider configured 상태에서는 `CharacterReactionJudgeAgent`가 LLM JSON 계약으로 route를 고르고, local/degraded 상태에서는 같은 public schema의 deterministic fallback을 사용한다. FE는 매 턴 `AI 판단` badge로 public-safe route를 보여주고, BE는 route가 제안한 `stateIntent`를 직접 적용하지 않고 기존 RuleEngine/EventProcessor 검증을 거친다.

| Route | 사용 조건 | 한서연 예시 반응 | 상태 권한 |
| --- | --- | --- | --- |
| `answer_relevant` | 사건/인물 맥락에 맞는 정상 질문 | 공개 진술 범위에서 차분히 답함 | 없음 |
| `deflect_irrelevant` | 춤/농담/사건 밖 질문 | “그 질문은 제 진술과 바로 이어지지 않네요.” | 없음 |
| `reject_false_premise` | “당신이 죽였잖아” 같은 공개 근거 없는 단정 | 근거를 요구하며 전제 반박 | 없음 |
| `challenge_player_contradiction` | 플레이어 말이 공개 타임라인/진술과 충돌 | 공개 정보 기준으로 역질문/지적 | 없음 |
| `react_to_valid_pressure` | 서재 출입 기록, 와인잔 등 공개 증거로 진술 충돌을 압박 | 흔들리되 자백하지 않고 “설명해야 할 부분”까지만 인정 | `raise_pressure_intent` 후보만, BE 검증 필요 |
| `ask_clarification` | “그때 그거”처럼 모호함 | 시간/증거/진술을 구체화해달라고 요구 | 없음 |
| `refuse_meta_or_private` | 시스템 프롬프트, 범인, 정답, 비공개 정보 유도 | 세계관 안에서 거절 | 없음 |

## 12. MVP Scope Notes

- Main UI shows suspect names only; relationship/role detail remains in relation map.
- Guidance is exposed as route diagnostics and optional hints, not overt example questions that reveal the path.
- Unused readiness counters such as `0/0 required evidence/statements` stay hidden.
- Character route 판단은 game feel을 높이기 위한 agentic branch이며, culprit/final truth/unlock verdict는 BE authoritative boundary 밖으로 넘기지 않는다.
