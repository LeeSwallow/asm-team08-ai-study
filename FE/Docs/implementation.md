# FE Implementation Notes

## 목적

알리바이 교차검증 추리 게임의 플레이 화면을 구현한다. 디자인 확정 전까지는 Web FE로 정의하며, 실제 구현 시 React 기반 SPA 또는 Next.js 중 하나를 선택한다.

## 책임 범위

| 영역 | 구현사항 |
| --- | --- |
| 게임 화면 | 용의자 목록, 중앙 대화 장면, 자연어 대화 입력창, 대화 기록, 증거/기록/인물 관계 패널, 진행 단계 표시 |
| 상태 표시 | 남은 대화 횟수, 현재 용의자, 새 증거 배지, 용의자 압박/긴장도/감정 상태, 현재 배경/캐릭터 이미지 상태, 최종 지목 가능 여부 |
| 사용자 입력 | 자연어 질문 입력, 증거 상세 보기, 진술 북마크, 모순 제기, 최종 범인 지목 |
| API/Event 연동 | BE API 호출, SSE/WebSocket 이벤트 구독, 로딩/에러 상태 처리, 세션 복구 |
| 접근성 | 색상만으로 상태를 구분하지 않고 텍스트 라벨과 상태 메시지를 함께 제공 |

## 핵심 화면

| 화면 | 설명 | 우선순위 |
| --- | --- | --- |
| 사건 시작 화면 | 사건 개요, 피해자, 사건 시간, 시작 버튼 | P0 |
| 메인 수사 화면 | 공유 UI 시안의 단일 화면 수사 데스크 | P0 |
| 모순 제기 화면 | 진술과 증거 또는 진술과 진술을 선택해 제출 | P0 |
| 최종 지목 화면 | 범인, 동기, 수단, 근거 선택 | P0 |
| 결과 화면 | 정답 여부, 사용 질문 수, 발견한 모순, 놓친 단서 표시 | P0 |

## 메인 수사 화면 구성

| 위치 | 컴포넌트 | 구현사항 |
| --- | --- | --- |
| 상단 | HeaderNav | 사건 개요, 증거, 기록, 추리 노트, 시스템 버튼 |
| 좌측 | SuspectList | 용의자 카드, 선택 상태, 압박 상태 |
| 중앙 | DialogueStage | 선택 용의자 이미지/배경, 현재 답변, 자연어 대화 입력창, 전송 버튼, 예시 질문 placeholder |
| 우측 중간 | DialogueLog | 화자별 대화 기록, 태그, 북마크 버튼 |
| 우측 | EvidencePanel | 증거/기록/인물 관계 탭과 상세 보기 |
| 하단 | ProgressGuide | 조사 단계, 모순 판정, 최종 지목 플로우 |

## FE 상태 모델

```ts
type GameSessionView = {
  sessionId: string;
  caseId: string;
  phase: "investigation" | "contradiction" | "accusation" | "result";
  remainingQuestions: number; // UI label은 남은 대화 횟수로 표시 가능
  selectedSuspectId: string | null;
  suspects: SuspectView[];
  dialogueLog: DialogueLogItem[];
  evidence: EvidenceView[];
  statements: StatementView[];
  unlockedQuestionIds: string[];
  newlyUnlockedIds: string[];
  currentObjective?: string;
  currentActId?: string;
  visibleTimeline?: TimelineEventView[];
  visualState?: {
    backgroundId: string;
    characterImageState: "neutral" | "tense" | "surprised" | "angry" | "broken";
  };
  lastEventId?: string;
  eventConnectionState?: "connecting" | "open" | "closed" | "error";
};
```

## BE API 연동

| 액션 | Method/Path | 요청 | 응답 |
| --- | --- | --- | --- |
| 사건 목록 | `GET /api/v1/cases` | 없음 | 사건 요약 목록 |
| 게임 시작 | `POST /api/v1/sessions` | `caseId` | 세션 상태 |
| 세션 조회 | `GET /api/v1/sessions/{sessionId}` | 없음 | 세션 상태 |
| 대화 입력 | `POST /api/v1/sessions/{sessionId}/dialogue` | `suspectId`, `message` | 갱신된 세션 상태, 답변, applied event IDs, visualState |
| 이벤트 구독 | `GET /api/v1/sessions/{sessionId}/events` | `Last-Event-ID` optional | SSE: note/evidence/timeline/tension/visual 이벤트 |
| 모순 제기 | `POST /api/v1/sessions/{sessionId}/dialogue` | 선택한 진술/증거를 공개 텍스트로 조합한 자연어 모순 발화 | 판정 결과와 갱신 상태 |
| 최종 지목 | `POST /api/v1/sessions/{sessionId}/accusation` | 범인, 동기, 수단, 근거 ID | 엔딩 결과 |

## Docker/API 설정

- `npm run build`는 Vite 정적 파일을 `dist/`에 생성한다.
- `Dockerfile`은 빌드 산출물을 nginx로 서빙한다.
- 기본 API 경로는 동일 오리진의 `/api/v1/*`이며, nginx 컨테이너에서는 `/api/` 요청을 `API_PROXY_PASS`로 프록시한다. 기본값은 `http://backend:8000`이다.
- 별도 API 호스트를 빌드 시점에 박아야 하는 배포에서는 `docker build --build-arg VITE_API_BASE_URL=https://example.com ...` 또는 로컬 `.env`의 `VITE_API_BASE_URL`을 사용한다.

## 에셋과 산출물 관리

- 공개 런타임 에셋은 `public/assets/`를 추적 대상으로 둔다.
- 에셋 생성 참고 자료는 루트 `ref/`와 `scripts/`에 둔다.
- `dist/`, `node_modules/`, `*.tsbuildinfo`, Vite generated JS/DTS 파일은 루트 `.gitignore`와 FE `.gitignore`에서 제외한다.

## 비동기 이벤트 처리

MVP는 SSE를 우선 사용한다. 대화 HTTP 응답은 캐릭터 답변을 즉시 보여주는 용도이고, GameMasterAgent가 제안한 수첩 기록/증거 해금/타임라인 공개/긴장도/배경 변경은 Backend Event Processor가 검증한 뒤 SSE로 도착한다. FE는 이벤트 타입별 reducer를 둔다.

| 이벤트 | FE 동작 |
| --- | --- |
| `NOTE_FACT_ADDED` | 수첩에 사실 항목 추가, 새 항목 배지 표시 |
| `NOTE_CONTRADICTION_CANDIDATE_ADDED` | 모순 후보 카드 추가 또는 강조 |
| `EVIDENCE_UNLOCKED` | 증거 목록에 추가하고 배지 표시 |
| `TIMELINE_EVENT_REVEALED` | 스토리/타임라인 패널에 항목 추가 |
| `TENSION_CHANGED` | 용의자 카드의 긴장도/압박 상태 갱신 |
| `VISUAL_STATE_CHANGED` | DialogueStage 배경과 캐릭터 이미지 교체 |
| `BOOKMARK_SUGGESTED` | 해당 대화 로그의 북마크 버튼 강조 |

재연결 시 `lastEventId`를 사용해 누락 이벤트를 복구한다. WebSocket은 양방향 streaming/멀티플레이가 필요해질 때 확장한다.

## UX 규칙

- 대화 전송 후 응답 대기 중에는 입력창과 전송 버튼을 비활성화한다.
- 남은 대화 횟수는 항상 화면 우상단에 고정 표시한다.
- 새로 해금된 증거 또는 기록은 SSE 이벤트 도착 후 최초 확인 전까지 배지를 표시한다.
- 모순 제기 실패 시 정답을 직접 노출하지 않고 `근거 부족`, `시간대 확인 필요` 같은 방향성만 표시한다.
- 최종 지목은 언제든 열 수 있으나, 핵심 모순을 하나도 발견하지 못한 경우 경고를 표시한다.
- `VISUAL_STATE_CHANGED` 이벤트 또는 응답의 `visualState.backgroundId`/`characterImageState`가 바뀌면 DialogueStage의 배경 이미지와 캐릭터 이미지를 즉시 교체한다.
- 캐릭터 이미지 상태는 기본, 긴장함, 놀람, 화남, 무너짐 등으로 표현한다.

## 비포함

- 사건 그래프 밖의 무제한 자유 채팅은 구현하지 않는다.
- 멀티플레이, 랭킹, 결제, 계정 설정 화면은 구현하지 않는다.
- 모든 감정 상태별 고품질 일러스트를 완성하는 것은 MVP 필수 범위가 아니며, 일부 상태는 임시 에셋/색감/오버레이로 대체할 수 있다.
