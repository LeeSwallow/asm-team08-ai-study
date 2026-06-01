# 구현 개요

## 폴더별 문서

| 폴더 | 문서 | 역할 |
| --- | --- | --- |
| `FE` | `FE/Docs/implementation.md` | 프론트엔드 화면, 상태, API 연동 구현사항 |
| `BE` | `BE/Docs/implementation.md` | FastAPI Backend API, 룰 엔진, 세션/저장, AI 엔진 통합 구현사항 |

## 서비스 구성

MVP는 2개 실행 단위로 구성된다.

| 영역 | 스택 | 책임 |
| --- | --- | --- |
| FE | React/Vite | 플레이 화면과 사용자 인터랙션 |
| BE | FastAPI + LangGraph | 게임 상태, 룰 판정, 저장, AI 엔진 (자연어 답변/힌트/요약/엔딩 해설) |

> AI 엔진 코드(`CharacterAgent → LightRuleCheck → GameMasterAgent`)는 `BE/app/ai_engine/` 서브패키지로 통합되어 있다. 별도 프로세스나 HTTP 경계 없이 BE 내부에서 직접 호출된다.

## 핵심 원칙

- 게임 정답 판정은 BE Rule Engine이 담당한다.
- AI 엔진은 자연어 생성과 요약을 담당하며 판정을 덮어쓰지 않는다.
- FE는 BE의 세션 상태를 단일 기준으로 렌더링한다.
- 사건 데이터는 코드와 분리해 JSON/DSL 형태로 관리한다.
