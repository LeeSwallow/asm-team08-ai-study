# Commit Convention

이 레포는 Conventional Commits를 사용한다. 모든 Codex 작업자는 변경 전후 `git status --short`를 확인하고, 커밋은 사용자가 명시적으로 요청한 경우에만 수행한다.

## Format

```text
<type>(<scope>): <imperative summary>

<body: optional, why/how/test 중심>
```

## Types

- `feat`: 사용자-visible 기능 추가
- `fix`: 버그 수정
- `refactor`: 동작 변경 없는 구조 개선
- `perf`: 성능 개선
- `test`: 테스트 추가/수정
- `docs`: 문서만 변경
- `build`: Docker, package, dependency, build 설정
- `ci`: CI/CD 설정
- `chore`: 잡무, 포맷, 생성물 정리
- `revert`: 이전 커밋 되돌림

## Scope rule

- BE: `api`, `domain`, `rule-engine`, `event-processor`, `infra`, `schemas`, `tests`, `docker`, `docs`
- FE: `ui`, `api`, `state`, `events`, `assets`, `styles`, `tests`, `docker`, `docs`
- AI: `dialogue-graph`, `guard`, `prompts`, `schemas`, `llm`, `hints`, `summary`, `ending`, `tests`, `docker`, `docs`

Examples:

```text
feat(event-processor): add validated SSE session event stream
fix(dialogue-graph): clear repaired fact-violation flag after safe fallback
refactor(ui): split investigation desk into focused panels
test(rule-engine): cover partial contradiction verdicts
```


## Atomic commit rule

커밋은 기능/도메인/계층별 최소 단위로 나눈다. 한 커밋은 한 가지 의도만 가져야 하며, 리뷰어가 쉽게 되돌리거나 이해할 수 있어야 한다.

원칙:

- 서로 다른 도메인 변경을 한 커밋에 섞지 않는다.
- `feat`와 `refactor`와 `test`를 무리하게 한 커밋에 합치지 않는다. 단, 같은 기능을 검증하는 최소 테스트는 해당 기능 커밋에 포함 가능하다.
- 대규모 작업은 docs/setup -> schema/contract -> domain/use-case -> API/infra -> FE wiring -> tests/refactor 순서처럼 추적 가능한 단위로 쪼갠다.
- generated/vendor/build output은 커밋하지 않는다. 예: `node_modules`, `dist`, `*.tsbuildinfo`, cache 파일.
- 커밋 전 `git diff --stat`과 `git diff --name-only`로 범위가 의도와 맞는지 확인한다.
- 각 커밋은 가능하면 독립적으로 build/test가 통과해야 한다.

권장 분할 예시:

```text
docs(architecture): add clean architecture quality gates
feat(schemas): add public storyline and visual state contracts
feat(event-processor): validate proposed dialogue events
feat(api): expose session dialogue and SSE event endpoints
refactor(api): extract dialogue use case from route handlers
test(event-processor): cover rejected hidden timeline events
```

## Quality gate before commit

커밋 전 다음을 실행한다.

- BE: `pytest -q`
- FE: `npm run build`
- AI: `pytest -q`

실패하면 커밋하지 말고 실패 로그와 원인/수정 계획을 보고한다.
