# Final Scenario and Event-Driven Architecture

## 최종 방향

Detective Agent는 선택지형 추리 게임이 아니라 “대화형 용의자 심문 + 증거/진술 모순 추리” 게임이다. 플레이어는 자연어로 질문하고, 내부 시스템은 사건 그래프와 캐릭터별 타임라인에 질문을 매핑해 일관된 답변과 공정한 판정을 제공한다.

핵심 AI Agent 구조는 다음 순서를 따른다.

1. CharacterAgent
   - 캐릭터 대화 생성 담당.
   - 선택된 용의자의 성격, 공개/해금된 개인 타임라인, 현재 긴장도, 감정 상태, background/character visualState를 반영한다.
   - 사건 데이터에 없는 새 사실을 만들지 않는다.
2. LightRuleCheck
   - 캐릭터가 이상한 대화를 하는지 검증한다.
   - 검증 범위: 사건 설정 위반, 공개되지 않은 진실 누설, 캐릭터별 타임라인 충돌, 감정/긴장도 불일치, 말투 붕괴.
   - 문제가 있으면 안전 답변으로 보정하거나 GameMasterAgent 기록 이벤트를 차단한다.
3. GameMasterAgent
   - 대화에서 드러난 캐릭터 정보, 단서 후보, 모순 후보, 감정 변화, 수첩 기록 후보를 추출한다.
   - 단, 세션 상태를 직접 동기 변경하지 않는다.
   - GameMasterAgent의 출력은 “상태 변경 명령”이 아니라 “도메인 이벤트 제안”이다.

## 시나리오 재구성

### 사건 제목
진실은, 서로의 말 속에 있다

### 공개 시나리오
폭풍우 치던 밤, 저택 2층 서재에서 강도준이 쓰러진 채 발견된다. 외부 침입 흔적은 없고, 저택 안에 있던 네 명의 인물은 서로 다른 알리바이를 주장한다. 플레이어는 자연어 대화로 각 인물의 말을 끌어내고, 증거와 진술을 비교해 “같은 시간에 동시에 성립할 수 없는 말”을 찾아야 한다.

### 비공개 진실
한서연은 상속 비율 변경 사실을 알고 피해자와 갈등했다. 22:02에 서재에 들어갔고, 22:05~22:07 정전 구간을 이용해 현장을 조작했다. 21:40에 멈춘 회중시계는 실제 사망 시각을 숨기기 위한 교란 단서다. 서재 출입 기록, 찢어진 유언장, 정전 기록, 한서연의 “22시 이후 계속 방에 있었다”는 진술이 핵심 모순 축이다.

### 주요 Act

| Act | 목표 | 플레이어 경험 | 해금/전환 조건 |
| --- | --- | --- | --- |
| intro | 사건 개요 파악 | 피해자, 서재, 초기 증거 확인 | 세션 시작 |
| alibi_collection | 각 인물의 알리바이 수집 | 자연어 질문으로 22시 전후 행적 확보 | 핵심 진술 2개 이상 확보 |
| first_break | 첫 모순 제기 | 한서연 방 진술 vs 서재 출입 기록 비교 | `con_room_claim_vs_entry_log` 정답 |
| pressure_unlock | 압박/감정 변화 | 한서연 긴장/분노 이미지 전환, 추가 기록 해금 | 압박 수치 상승 이벤트 |
| motive_reveal | 동기 확정 | 찢어진 유언장과 유언장 변경 예약 기록 연결 | 상속 관련 단서 해금 |
| final_accusation | 최종 지목 | 범인, 동기, 수단, 근거 제출 | 최종 지목 |

## 전체 사건 타임라인

| 시간 | 실제 사건 | 공개/해금 방식 | 관련 단서 |
| --- | --- | --- | --- |
| 21:30 | 피해자가 약을 복용. 치명적 약물 반응은 없음 | 박민규 심문 후 해금 | `ev_medicine_box` |
| 21:40 | 회중시계가 멈춘 것처럼 현장에 남음. 실제 사망 시각 은폐용 | 초기 공개 | `ev_broken_watch` |
| 21:55 | 피해자가 최윤아에게 전화해 다음 날 일정/유언장 관련 지시 | 최윤아 심문 후 해금 | `ev_phone_call`, `rec_will_revision_notice` |
| 22:00 | 피해자가 서재에 있음. 한서연은 방에 있었다고 주장 | 한서연 대화로 확보 | `st_hanseoyeon_room_2200` |
| 22:02 | 한서연이 서재에 출입 | 초기 증거로 공개 | `ev_study_entry_log` |
| 22:05~22:07 | 정전 발생. 한서연이 현장 일부를 조작 | 윤재호 심문 후 해금 | `ev_storm_blackout` |
| 22:10 | 윤재호가 서재 문이 열려 있는 것을 발견 | 초기 진술 | `st_yoonjaeho_found_2210`, `rec_hallway_patrol` |

## 캐릭터별 개인 타임라인

### 한서연

| 시간 | 실제 행적 | 주장/알리바이 | 감정 변화 | 모순 축 |
| --- | --- | --- | --- | --- |
| 21:55 | 유언장 변경 관련 갈등을 알고 불안해짐 | 상속 문제는 다툼일 뿐이라고 축소 | tense | `st_hanseoyeon_no_reason` vs `ev_torn_will` |
| 22:00 | 서재 근처로 이동 준비 | “제 방에 있었다” | neutral → tense | `st_hanseoyeon_room_2200` |
| 22:02 | 서재 출입 | 방에 있었다고 거짓 주장 | tense → surprised | `ev_study_entry_log`와 직접 충돌 |
| 22:05~22:07 | 정전 중 현장 조작 | 정전 얘기를 회피 | angry/broken | `ev_storm_blackout`, `ev_broken_watch` |

### 윤재호

| 시간 | 실제 행적 | 주장/알리바이 | 감정 변화 | 역할 |
| --- | --- | --- | --- | --- |
| 21:50 | 저택 순찰 중 유언장 변경 분위기를 감지 | 모른 척함 | neutral | 동기 단서 보조 |
| 22:05 | 정전 상황을 확인하러 이동 | 관리실 확인 중이었다고 설명 | tense | 정전 기록 해금 |
| 22:10 | 서재 앞에서 피해자 발견 | 최초 발견자 진술 | neutral | 발견 시각 기준점 |

### 박민규

| 시간 | 실제 행적 | 주장/알리바이 | 감정 변화 | 역할 |
| --- | --- | --- | --- | --- |
| 21:30 | 피해자의 약 복용 기록 확인 | 처방 문제는 없었다고 주장 | tense | 약물 범행 가능성 배제 |
| 22:00 | 손님방에서 의료 기록 정리 | 손님방에 있었다고 주장 | neutral | 대체 용의자/페이크 |

### 최윤아

| 시간 | 실제 행적 | 주장/알리바이 | 감정 변화 | 역할 |
| --- | --- | --- | --- | --- |
| 21:55 | 피해자와 통화. 유언장 변경 일정 일부를 들음 | 직접 만나지 않았다고 주장 | tense | 유언장 변경 단서 해금 |
| 22:00 | 응접실에서 문서 정리 | 응접실에 있었다고 주장 | neutral | 동기 배경 제공 |

## Visual State 규칙

| 상태 | 조건 | background | characterImageState |
| --- | --- | --- | --- |
| neutral | 일반 알리바이 수집 | `mansion_study_night` | `neutral` |
| tense | 같은 의미의 반복 질문, 민감한 주제 질문 | 어두운 조도/빗소리 강조 | `tense` |
| surprised | 증거 제시 또는 직접 모순 제기 직후 | 번개/흔들림 효과 | `surprised` |
| angry | 압박 수치 상승 후 회피/반박 | 붉은 톤 오버레이 | `angry` |
| broken | 핵심 모순 정답 후 | 배경 대비 감소/정적 | `broken` |

## Event-driven GameMasterAgent 구조

GameMasterAgent는 UI 상태를 직접 바꾸지 않는다. GameMasterAgent는 Backend에 event proposal을 반환하고, Backend의 Event Processor가 검증/저장/발행한다.

### 이벤트 처리 흐름

1. FE가 `POST /api/v1/sessions/{sessionId}/dialogue`로 자연어 메시지를 보낸다.
2. BE가 사건 그래프/캐릭터 타임라인으로 허용 진술 범위와 visualState를 계산한다.
3. BE가 AI Service의 `/internal/v1/dialogue/respond`를 호출한다.
4. AI Service가 CharacterAgent → LightRuleCheck → GameMasterAgent 순서로 처리한다.
5. GameMasterAgent는 `proposedEvents[]`를 반환한다.
6. BE Event Processor가 이벤트를 검증한다.
7. 검증된 이벤트를 event store/session repository에 저장한다.
8. BE가 HTTP 응답으로 기본 대화 결과를 즉시 반환한다.
9. BE가 SSE 또는 WebSocket으로 UI에 비동기 이벤트를 발행한다.
10. FE는 이벤트를 받아 수첩, 증거 배지, 타임라인, 캐릭터 이미지, 배경을 업데이트한다.

### 이벤트 타입

| eventType | 설명 | UI 반영 |
| --- | --- | --- |
| `NOTE_FACT_ADDED` | 대화에서 새 사실이 사건노트에 기록됨 | 수첩에 항목 추가 |
| `NOTE_CONTRADICTION_CANDIDATE_ADDED` | 모순 후보가 기록됨 | 수첩/모순 패널 강조 |
| `EVIDENCE_UNLOCKED` | 증거가 공개됨 | 증거 탭 배지 표시 |
| `TIMELINE_EVENT_REVEALED` | 공개 타임라인 항목이 해금됨 | 타임라인 패널 추가 |
| `TENSION_CHANGED` | 용의자 긴장도 변경 | 캐릭터 상태/말투 변경 |
| `VISUAL_STATE_CHANGED` | 배경 또는 캐릭터 이미지 변경 | DialogueStage 이미지 교체 |
| `BOOKMARK_SUGGESTED` | 중요한 발언 북마크 제안 | 대화 로그 북마크 버튼 강조 |

### SSE 권장안

MVP는 SSE를 우선한다. 서버→클라이언트 단방향 이벤트만 필요하고 구현이 WebSocket보다 단순하기 때문이다.

Endpoint:

```text
GET /api/v1/sessions/{sessionId}/events
Accept: text/event-stream
```

SSE payload 예시:

```text
event: NOTE_FACT_ADDED
data: {"eventId":"evt_001","sessionId":"session_001","payload":{"text":"한서연은 22시 이후 방에 있었다고 주장했다.","sourceDialogueId":"dlg_001"}}
```

WebSocket은 추후 실시간 공동 플레이 또는 양방향 agent streaming이 필요할 때 확장한다.

## 구현 기준

- GameMasterAgent output은 `proposedEvents[]`이며 직접 DB를 수정하지 않는다.
- BE만 세션 상태를 변경한다.
- 모든 이벤트는 `eventId`, `sessionId`, `type`, `payload`, `source`, `createdAt`, `visibility`, `applied`를 가진다.
- FE는 HTTP 응답으로 대화 텍스트를 먼저 표시하고, SSE 이벤트로 수첩/증거/visualState를 비동기 반영한다.
- 이벤트 재연결 시 FE는 마지막 `eventId`를 기준으로 누락 이벤트를 복구한다.
