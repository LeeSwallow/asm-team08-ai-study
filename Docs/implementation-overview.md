# Implementation Overview

## 폴더별 문서

| 폴더 | 문서 | 역할 |
| --- | --- | --- |
| `FE` | `FE/Docs/implementation.md` | 프론트엔드 화면, 상태, API 연동 구현사항 |
| `BE` | `BE/Docs/implementation.md` | FastAPI Backend API, 룰 엔진, 세션/저장 구현사항 |
| `AI` | `AI/Docs/implementation.md` | FastAPI + LangGraph AI Service 구현사항 |
| `Design` | `Design/Docs/implementation.md` | 디자인 방향, 컴포넌트, 레이아웃 구현 기준 |

## 서비스 구성

MVP는 3개 실행 단위와 1개 디자인 산출 영역으로 나눈다.

| 영역 | 스택 | 책임 |
| --- | --- | --- |
| FE | Web FE | 플레이 화면과 사용자 인터랙션 |
| BE | FastAPI | 게임 상태, 룰 판정, 저장, AI Service 호출 |
| AI | FastAPI + LangGraph | 자연어 답변, 힌트, 요약, 엔딩 해설 |
| Design | Figma 또는 정적 명세 | UI 구조와 디자인 시스템 |

## 핵심 원칙

- 게임 정답 판정은 BE Rule Engine이 담당한다.
- AI는 자연어 생성과 요약을 담당하며 판정을 덮어쓰지 않는다.
- FE는 BE의 세션 상태를 단일 기준으로 렌더링한다.
- 사건 데이터는 코드와 분리해 JSON/DSL 형태로 관리한다.
- 디자인 확정 전에는 FE 스택과 세부 UI 라이브러리를 고정하지 않는다.
