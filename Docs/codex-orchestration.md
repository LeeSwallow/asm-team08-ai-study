# Codex 오케스트레이션 컨텍스트 — Detective Agent

## 현재 저장소 구조

이 워크스페이스는 하나의 루트 Git 저장소 아래에 있는 멀티 디렉터리 프로젝트다.

- `BE/`: FastAPI Backend. 세션, 룰 엔진, 안전한 공개 페이로드, AI 엔진, Event Processor/SSE의 단일 진실 공급원.
  - `BE/app/ai_engine/`: CharacterAgent → LightRuleCheck → GameMasterAgent AI 처리 로직. 별도 프로세스 없이 BE 내부에서 직접 호출된다.
- `FE/`: React/Vite 프론트엔드. 단일 화면 수사 데스크, 자연어 대화, BE API + SSE 소비.

## 보존해야 할 제품 방향

MVP는 자연어 탐정 시뮬레이션이다. 선택지 버튼 퀴즈로 만들지 않는다. 안정적인 설계는 다음과 같다:

`CharacterAgent → LightRuleCheck → GameMasterAgent(proposedEvents) → BE Event Processor(검증/적용) → SSE → FE 상태 업데이트`

BE는 룰 판정과 상태 변경의 권위자다. AI 엔진은 룰을 덮어쓰지 않는다. FE는 BE 상태를 반영한다.

## FE 비주얼 목표

FE는 `FE/target/chatgpt-shared-detective-interface.png`를 최대한 근접하게 구현해야 한다. FE Codex 작업을 오케스트레이션할 때 이 이미지를 주요 UI 레퍼런스로 삼고, FE 에이전트가 완료 보고 전 렌더링된 첫/기본 화면을 이미지와 비교하도록 요청한다. 목표는 상단 네비, 왼쪽 용의자 카드, 중앙 심문 장면/입력창, 오른쪽 증거 그리드 + 모순 패널, 하단 내부 처리 흐름 스트립이 있는 다크 누아르 수사 대시보드다.

## Codex 에이전트용 추가 문서

- `BE/AGENTS.md`, `BE/SKILL.md`, `BE/Docs/commit-convention.md`
- `FE/AGENTS.md`, `FE/SKILL.md`, `FE/Docs/commit-convention.md`

## 오케스트레이션 프로토콜

1. 새 작업 전송 전 tmux 창 캡처.
2. 담당 저장소 에이전트에게 먼저 작업 할당. 중앙 통합/검증이 필요하지 않으면 전문가 코드를 직접 수정하지 않는다.
3. 에이전트에게 변경된 파일, 검증 명령, 실패, 크로스 저장소 계약 변경 보고 요청.
4. 에이전트 완료 후 중앙에서 검증:
   - BE: `pytest -q`
   - FE: `npm run build`
5. 계약이 변경되면 `BE/Docs/implementation.md`를 업데이트하고 상대 에이전트에게 정확한 스키마/엔드포인트 델타를 알린다.

## 코드 스멜 및 관찰 가능성 기준

모든 저장소에서 최소화해야 할 것:

- 크고 복잡한 파일/함수
- 중복된 페이로드 매핑
- 숨겨진 클라이언트/서버 진실 불일치
- 타입되지 않은 요청/응답 블롭
- 조용한 광범위 예외 삼킴
- 기밀/비공개 사건 진실/플레이어 자유 입력을 기본적으로 포함하는 로그

모든 저장소에서 추가해야 할 것: 요청/세션/사건 ID, 지속시간, 결정/이벤트 메타데이터, fallback/오류 이유가 포함된 구조화 로그.
