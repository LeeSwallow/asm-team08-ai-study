# PRD 기반 구조 감사 결과

## 결론

최종 제품 방향은 “선택지 클릭형”이 아니라 “대화형 인터페이스 + 진술/증거 조합 추리”다. 단, 무제한 자유 채팅이 아니라 사건 그래프와 캐릭터별 타임라인을 기반으로 자연어 질문을 의미 매핑하고, CharacterAgent → LightRuleCheck → GameMasterAgent 구조로 답변/검증/이벤트 제안을 처리한다. GameMasterAgent의 상태 변경은 동기 직접 변경이 아니라 Backend Event Processor 검증 후 SSE/WebSocket으로 UI에 비동기 반영한다.

기존 구현은 시각적으로 질문 버튼이 퀴즈 선택지처럼 보이고, 캐릭터별 타임라인/visualState/GameMasterAgent 이벤트 제안 구조가 문서에 충분히 반영되지 않았다.

## 문서 기준 핵심 구조

- PRD 6장: 사건 개요 → 용의자 선택/질문 → 대화 기록 저장 → 증거/기록 교차검증 → 모순 제기 → 압박/해금 → 최종 지목 → 엔딩 피드백.
- PRD F-020: MVP는 자연어 질문 입력 기반 대화형 인터페이스 제공.
- PRD F-023: 용의자 답변은 사건 데이터의 진술 노드 및 캐릭터별 타임라인과 연결.
- PRD F-050~F-053: 진술+증거 조합을 룰 엔진이 판정하고, 정답/부분정답 시 압박 및 해금.
- PRD F-070~F-073: AI는 CharacterAgent, LightRuleCheck, GameMasterAgent로 대화 생성/검증/이벤트 제안을 담당하되, 최종 판정과 상태 적용은 룰 엔진/Event Processor를 덮어쓰지 않음.
- PRD 12.2~12.4: FE/BE/AI 3서비스 분리. BE가 단일 진실 공급원, AI는 BE 내부 호출만.

## 구현 대조

### FE

충족:
- 단일 화면 수사 데스크 구성.
- 용의자 목록, 중앙 대화 장면, 대화 기록, 증거/기록/관계 탭, 추리 노트/모순/최종 지목 영역 존재.
- 질문 제한 및 남은 횟수 표시.
- 진술/증거 선택으로 모순 제기 가능.
- Docker frontend 서비스 제공.
- 생성된 배경/캐릭터 에셋 표시.

갭:
- 질문 영역이 “대화형 탐문”보다 “버튼 선택지”처럼 강하게 보인다. 최종 방향은 채팅 입력창 중심이며, 추천 질문은 선택지 강제가 아니라 placeholder/예시/자동완성 힌트로만 사용한다.
- background 이미지와 캐릭터 이미지는 긴장도/감정 상태에 따라 바뀌어야 한다.
- 수첩 기록/증거 해금/visualState 변경은 SSE 이벤트로 비동기 반영해야 한다.
- P1 기능인 대화 로그 북마크 API 연동은 미흡하다. 현재 노트 추가는 로컬 textarea 중심이다.
- 증거 상세에서 관련 진술 후보를 보여주는 F-043이 약하다.
- 최종 지목의 motive/method 텍스트는 BE 판정에 사용되지 않는다. 현재 BE는 핵심 근거 ID 중심으로 판정한다.

### BE

충족:
- 사건 JSON 로딩, 세션 생성/조회, 질문 제한, 대화 로그, 해금, 모순 판정, 최종 지목 API 존재.
- RuleEngine이 정답/부분/근거부족/오답을 deterministic하게 판정.
- 압박 수치와 해금 ID를 관리.
- 테스트 통과: `PYTHONPATH=. pytest -q` 2 passed.

수정 완료:
- `visible_session_payload`와 `/cases/{case_id}`에서 `secret`, `isCulprit` 필드가 FE/API로 노출되던 문제 제거.
- BE→AI dialogue payload가 AI 스키마와 맞지 않아 422를 유발하던 문제 수정. 이제 `suspect`, `question`, `allowedStatement`, `style`, `revealAllowed` 구조로 호출.

남은 갭:
- `AskQuestionRequest`에는 suspectId가 없고 FE는 extra로 보내고 있다. 동작에는 문제 없지만 계약 명확화를 위해 제거하거나 스키마에 명시하는 편이 좋다.
- 최종 지목 request schema에 motive/method가 없어 PRD F-060의 “동기/수단 제출”이 판정 데이터로 보존되지 않는다.
- 서버 테스트 실행 시 기본 `pytest`는 PYTHONPATH 문제로 실패할 수 있다. pyproject 또는 pytest.ini로 pythonpath 설정 필요.

### AI 엔진 (BE 내부 통합)

충족:
- `BE/app/ai_engine/` 서브패키지로 통합. 별도 프로세스/포트 없이 BE에서 직접 호출.
- dialogue/hint/summary/ending graph 존재.
- Dialogue는 allowedStatement 기반으로만 답변을 재작성하고 guard로 사건 사실 추가를 차단.
- AI 실패 시 deterministic fallback 구조 존재.
- BE 테스트 30개 통과 (AI 엔진 포함).

변경 완료:
- `LocalAIClient`가 HTTP 기반 `AIClient`를 대체하여 graph 함수를 직접 Python 함수 호출.
- `BE/app/ai_engine/core/config.py`가 동일한 `AI_*` 환경 변수를 읽음.
- `BE/pyproject.toml`에 `langgraph` 의존성 추가.

남은 갭:
- 현재 guard는 LLM이 부가 표현을 시도했다가 최종 텍스트가 allowedStatement로 축약된 경우 safety.violatesCaseFacts=true를 유지할 수 있다. 보안적으로는 안전하지만 UI/로그에 표시한다면 혼동될 수 있다.
- Hint/summary/ending은 FE에서 적극적으로 호출되지 않는다.

## 실제 검증

- BE unit/smoke: 통과.
- AI tests: 통과.
- FE build: 통과.
- Docker compose build/up: 통과.
- 서비스 상태:
  - AI: healthy, 8001
  - Backend: healthy, 8000
  - Frontend: running, 8080
- API 플로우:
  - 세션 생성 정상.
  - 대화 입력 시 remainingQuestions/remainingDialogues 감소 및 dialogueLog 추가가 필요.
  - 핵심 모순 제출 시 correct 판정, 압박 상승, 새 진술/질문/증거 해금 정상.
  - 최종 지목 correct 판정 정상.
- 비밀 필드 노출:
  - `/api/v1/cases/case_001`: secret key 없음, isCulprit key 없음.
  - `/api/v1/sessions`: secret key 없음, isCulprit key 없음.

## 권장 다음 수정

1. FE 질문 UI를 선택지 버튼에서 자연어 탐문 입력창으로 바꾼다. 내부는 message를 questionIntent/statement/timeline에 매핑해 룰 안정성을 지킨다.
2. `DialogueEntry`에 statementId/time/place 태그와 visualState를 저장하고, 수첩 업데이트는 GameMasterAgent `proposedEvents[]` → Event Processor → SSE 이벤트로 반영한다.
3. 노트 저장/북마크/요약 버튼을 FE에서 실제 BE API와 연결하고, `GET /sessions/{id}/events` SSE 구독으로 수첩/증거/타임라인 이벤트를 처리한다.
4. `AccusationRequest`에 motive/method를 추가해 최종 지목 제출 내용을 세션에 보존한다.
5. pytest 기본 실행이 통과하도록 BE에 pytest.ini 또는 pyproject 설정을 추가한다.
