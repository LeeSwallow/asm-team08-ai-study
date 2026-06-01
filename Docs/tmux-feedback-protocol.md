# tmux 에이전트 간 피드백 프로토콜

목적: BE, FE 에이전트가 수동 사용자 개입 없이 tmux를 통해 오케스트레이터와 다른 도메인 에이전트에게 실행 가능한 피드백을 전달할 수 있어야 한다.

## 역할 및 창

- 오케스트레이터 창: `orchest:1.1`
- Backend 창: `BE:1.1`
- Frontend 창: `FE:1.1`

각 전문가는 자신의 저장소를 소유하며, 일반적으로 다른 저장소를 직접 편집하지 않는다. 크로스 도메인 이슈는 이 프로토콜을 통해 보고한다.

## 피드백을 보내야 하는 경우

다음 중 하나라도 발생하면 피드백을 보낸다:

1. **계약 불일치**
   - 엔드포인트 경로, 메서드, 요청/응답 스키마, SSE 이벤트 형태, 필드명, 열거형, 오류 처리가 다른 도메인과 일치하지 않음.

2. **통합 차단**
   - BE-FE 또는 FE-BE 흐름이 다른 도메인의 동작 누락 또는 호환되지 않는 데이터로 인해 실행 불가.

3. **보안/안전 우려**
   - 숨겨진 진실, 비공개 타임라인, 정답, 비밀, API 키, 전체 프롬프트, 플레이어 자유 입력 전문이 페이로드/로그/클라이언트 픽스처를 통해 노출될 가능성.

4. **아키텍처/코드 스멜 우려**
   - 다른 도메인의 계약이 중복 상태, BE 권위 우회, FE의 가짜 프로덕션 진실 강제, AI의 상태 권위화를 조장함.

5. **관찰 가능성 갭**
   - E2E 흐름 디버깅을 위해 다른 도메인에서 request_id/session_id/event_id/fallback/로그 필드가 필요한 경우.

6. **커밋/dogfood 차단**
   - 다른 도메인이 수정 또는 확인하기 전까지 마일스톤을 commit-ready로 볼 수 없는 경우.

## 피드백 메시지 형식

수신 에이전트와 오케스트레이터가 빠르게 분류할 수 있도록 다음 형식을 사용한다:

```text
[CROSS-FEEDBACK]
from: BE|FE
to: ORCH|BE|FE|ALL
severity: blocker|high|medium|low
category: contract|integration|safety|observability|architecture|dogfood|commit
summary: 한 줄 실행 가능한 요약
context:
- 관련 저장소/파일/함수/엔드포인트/이벤트
- 관찰된 동작 또는 누락된 동작
- 기대하는 동작
request:
- 필요한 정확한 변경 또는 확인
validation:
- 수정을 증명하는 명령, API 호출, 브라우저 흐름, 테스트
commit impact:
- commit-ready 차단 여부: yes|no
- 알려진 경우 영향을 받는 원자 마일스톤/메시지
```

## tmux를 통한 피드백 전송 방법

권장: 대상 창과 오케스트레이터 창에 짧은 `/steer` 메시지를 붙여 넣는다.

예시, FE에서 BE와 오케스트레이터로 전송:

```bash
tmux send-keys -t BE:1.1 "/steer [CROSS-FEEDBACK] from: FE to: BE severity: blocker category: contract summary: dialogue 응답에 visualState 누락 ..." C-m
tmux send-keys -t orchest:1.1 "/steer [CROSS-FEEDBACK] from: FE to: BE severity: blocker category: contract summary: dialogue 응답에 visualState 누락 ..." C-m
```

멀티라인 피드백의 경우 임시 파일에 작성하고, tmux 버퍼에 로드한 후 대상 창에 붙여 넣고 Enter를 누른다:

```bash
tmux load-buffer -b cross_feedback /tmp/cross_feedback.txt
tmux paste-buffer -b cross_feedback -t BE:1.1
tmux send-keys -t BE:1.1 C-m
tmux paste-buffer -b cross_feedback -t orchest:1.1
tmux send-keys -t orchest:1.1 C-m
```

에이전트는 진행 중인 작업을 방해하지 않도록 메시지를 짧게 유지한다. 대상 창이 명확히 `Working` 상태이면 `orchest:1.1`에만 보내고 `to:`를 의도한 도메인으로 표시한다. 오케스트레이터가 안전한 시점에 전달한다.

## 라우팅 규칙

- 크로스 도메인 피드백에는 항상 오케스트레이터(`orchest:1.1`)를 참조에 포함한다.
- 수신 도메인이 유휴 또는 프롬프트 상태이면 해당 도메인에 직접 보내고 오케스트레이터에 복사한다.
- 수신 도메인이 활발히 작업 중이면 방해를 피하기 위해 오케스트레이터에만 보낸다. 오케스트레이터가 나중에 큐에 넣거나 전달한다.
- 피드백이 모든 도메인이나 공유 계약에 영향을 주면 `to: ALL`로 설정하고 오케스트레이터에 복사한다.
- 피드백이 커밋/dogfood 차단이면 `severity: blocker`와 `commit-ready 차단: yes`를 사용한다.

## 오케스트레이터 의무

`[CROSS-FEEDBACK]` 수신 시:

1. 행동 전 관련 창 캡처.
2. `Docs/orchestration-status.md`에 피드백 기록.
3. 수신 창을 유휴/작업중/차단/완료로 분류.
4. 안전하게 방해할 수 있을 때만 담당 에이전트에게 전달하거나, 상태 로그에 큐에 넣는다.
5. 담당 에이전트에게 변경된 파일, 검증 결과, 계약 델타, commit-ready 영향을 요청한다.
6. 완료 수락 전 API/브라우저/SSE/통합 dogfood를 통해 중앙에서 수정을 검증한다.

## 수락 기준

이 프로토콜은 다음 조건이 모두 충족될 때만 활성화된다:

- `BE/AGENTS.md`와 `FE/AGENTS.md`가 이 문서를 참조한다.
- 각 에이전트의 완료 보고에 보낸/받은 크로스 피드백이 포함되거나 명시적으로 `cross-feedback: none`이라고 명시한다.
- 오케스트레이터 로그에 차단 피드백과 라우팅 결정이 기록된다.
- Commit-ready 보고에 미해결 크로스 피드백이 마일스톤을 차단하는지 포함된다.
