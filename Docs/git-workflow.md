# Git 운영 및 리뷰 절차

이 저장소는 루트 디렉터리 하나만 Git 저장소로 사용한다. `BE/`, `FE/`, `Docs/` 내부에는 별도 `.git`을 만들지 않는다.

원격 저장소:

```bash
git remote add origin https://github.com/142spp/asm-team06-ai-study.git
```

## 브랜치 전략

기본 통합 브랜치는 `dev`로 둔다. 모든 기능, 수정, 문서 변경은 작업 브랜치에서 PR을 거쳐 `dev`에 merge한다. `main`은 발표, 배포, 제출 등 안정화된 스냅샷이 필요할 때만 `dev`에서 승격한다.

```text
main
  ^
  | release PR
dev
  ^
  | feature/fix/docs PR
feature/*, fix/*, docs/*, test/*, refactor/*, chore/*
```

## 기본 원칙

- 작업 단위는 Issue 하나를 기준으로 잡는다.
- 브랜치는 Issue 단위 또는 더 작은 변경 단위로 분리한다.
- 커밋은 리뷰 가능한 최소 단위로 나눈다.
- 하나의 PR은 하나의 목적만 가진다.
- 모든 변경사항은 PR 리뷰를 거쳐 `dev`에 저장한다.
- `dev`에 merge된 뒤에는 원격/로컬 작업 브랜치를 정리한다.
- 기능 변경과 리뷰/문서화 변경은 병행하되, 커밋 목적은 분리한다.

## 브랜치 규칙

브랜치 이름은 다음 형식을 사용한다.

```text
<type>/<issue-number>-<short-topic>
```

예시:

```text
feat/12-session-restore
fix/18-ai-timeout-fallback
docs/21-git-workflow
chore/25-compose-cleanup
```

권장 type:

- `feat`: 기능 추가
- `fix`: 버그 수정
- `docs`: 문서 변경
- `test`: 테스트 추가/수정
- `refactor`: 동작 변경 없는 구조 개선
- `chore`: 설정, 빌드, 운영성 작업

## 작업 흐름

1. 최신 `dev`를 기준으로 시작한다.

```bash
git switch dev
git pull origin dev
```

2. Issue를 생성한다.

```bash
gh issue create \
  --title "feat: 세션 복구 API 추가" \
  --body "목표, 범위, 검증 방법을 적는다."
```

3. Issue 번호로 브랜치를 만든다.

```bash
git switch -c feat/12-session-restore
```

4. 최소 단위로 수정하고 리뷰 관점의 문서도 함께 갱신한다.

```bash
git status --short
git diff
```

5. 관련 파일만 스테이징한다.

```bash
git add BE/app/application/session_commands.py BE/tests/test_api_smoke.py
```

6. 의미 있는 최소 단위로 커밋한다.

```bash
git commit -m "feat(be): add session restore command"
```

7. 필요한 검증과 리뷰 체크를 실행한다.

```bash
cd BE && uv run pytest -q
cd ../FE && npm run build
git diff --check
```

8. 원격 브랜치로 push한다.

```bash
git push -u origin feat/12-session-restore
```

9. PR을 생성한다.

```bash
gh pr create \
  --base dev \
  --head feat/12-session-restore \
  --title "feat(be): 세션 복구 API 추가" \
  --body "Closes #12"
```

10. 리뷰와 CI를 통과하면 merge한다.

```bash
gh pr merge --squash --delete-branch
```

11. 로컬을 정리한다.

```bash
git switch dev
git pull origin dev
git branch --delete feat/12-session-restore
```

12. 안정화가 끝난 `dev`는 별도 release PR로 `main`에 반영한다.

```bash
gh pr create \
  --base main \
  --head dev \
  --title "release: dev 통합본 반영" \
  --body "검증 완료된 dev 통합본을 main에 반영한다."
```

## 커밋 분리 기준

다음 기준 중 하나라도 다르면 커밋을 나눈다.

- 변경 목적이 다르다.
- 수정 대상 서비스가 다르다. 예: `AI`, `BE`, `FE`, `Docs`
- 동작 변경과 리팩터링이 섞인다.
- 테스트 보강과 구현 변경을 분리하면 리뷰가 쉬워진다.
- 설정 변경이 기능 구현과 독립적으로 검증 가능하다.

좋은 예:

```text
feat(be): add session restore command
test(be): cover session restore response
feat(fe): reconnect restored session state
docs: document session restore flow
```

피해야 할 예:

```text
update files
fix stuff
feat: change ai be fe docs
```

## PR 체크리스트

PR 본문에는 다음 내용을 포함한다.

```markdown
## 요약
- 변경한 핵심 내용을 적는다.

## 검증
- 실행한 테스트와 빌드 명령을 적는다.

## 리뷰 메모
- 설계상 선택, 위험, 후속 작업을 적는다.

## 영향 범위
- 영향을 받는 서비스나 API를 적는다.

Closes #<issue-number>
```

merge 전 확인 사항:

- `git status --short`에 의도하지 않은 파일이 없다.
- 관련 테스트 또는 빌드가 통과했다.
- PR이 연결된 Issue를 닫도록 `Closes #번호`를 포함했다.
- 한 PR에 여러 목적의 변경이 섞이지 않았다.
- README 또는 `Docs/`에 변경 이유와 사용 방법이 반영됐다.

## 변경 검토와 문서화 기준

변경사항마다 다음 관점으로 검토한다.

- 요구사항: PRD 또는 Issue의 목표와 직접 연결되는가.
- 구조: `BE`, `BE/app/ai_engine`, `FE`, `Docs` 중 책임 경계가 적절한가.
- 계약: API 요청/응답, 이벤트, 데이터 파일 형식이 문서와 일치하는가.
- 검증: 테스트, 빌드, 수동 확인 중 어떤 증거로 동작을 증명했는가.
- 운영: 환경 변수, Docker, 캐시, 로컬 산출물이 Git에 섞이지 않는가.
- 보안: `.env`, `.secret`, 키, 세션 데이터가 커밋되지 않는가.

리뷰 메모가 길어지면 해당 서비스의 `Docs/review-*.md` 또는 루트 `Docs/` 문서에 남긴다. 단기 메모와 오케스트레이션 산출물은 `.hermes/`에 둘 수 있지만 Git에는 올리지 않는다.

## 루트 저장소 유지 규칙

- `BE/.git`, `FE/.git`, `Docs/.git`을 다시 만들지 않는다.
- 외부 예제 저장소를 가져올 때는 `git clone` 대신 필요한 파일만 복사하거나, 별도 `ref/` 하위에 Git 메타데이터 없이 둔다.
- 서브모듈이 필요하면 팀 합의 후 `git submodule`로 명시적으로 추가한다.
