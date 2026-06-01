# Repository Integration Review

작성일: 2026-06-01

## 목적

기존 `AI/`, `BE/`, `FE/`, `Docs/` 하위 폴더별 Git 저장소를 제거하고, 루트 디렉터리 하나를 기준으로 개발/리뷰/문서화/merge 흐름을 통합한다. 최종 통합 브랜치는 `dev`로 둔다.

## 변경 요약

- 루트 저장소를 Git 저장소로 초기화했다.
- `origin`을 `git@github.com:LeeSwallow/asm-team08-ai-study.git`로 설정했다.
- 하위 폴더별 `.git` 메타데이터를 제거하고 루트 `.git`만 유지했다.
- 루트 `.gitignore`를 Python, Node, 빌드 산출물, 캐시, 세션 데이터, 비밀 파일, 로컬 오케스트레이션 산출물 기준으로 정리했다.
- README를 프로젝트 소개, 서비스 구조, 데이터 흐름, 디렉터리 구조, 실행/검증, Git 운영 중심으로 재작성했다.
- `Docs/git-workflow.md`에 `dev` 중심 브랜치 전략, 최소 커밋 기준, Issue/PR/merge 절차, 리뷰 체크리스트를 정의했다.

## 변경 묶음

| Issue | Branch | 범위 |
| --- | --- | --- |
| `#1` | `chore/1-root-repo-ops` | 루트 Git 운영, `.gitignore`, README, Docker Compose, workflow 문서 |
| `#2` | `feat/2-ai-uv-service` | AI 서비스 코드와 `uv` 기반 Python 프로젝트 구성 |
| `#3` | `feat/3-be-uv-service` | Backend 서비스 코드와 `uv` 기반 Python 프로젝트 구성 |
| `#4` | `feat/4-fe-app-assets` | Frontend 앱, 공개 에셋, nginx/Docker 구성 |
| `#5` | `docs/5-product-contracts` | PRD, 시나리오, 서비스 계약, 아키텍처 문서 |

## 검토 결과

### 저장소 구조

- `AI`, `BE`, `FE`, `Docs`는 일반 디렉터리로 유지한다.
- 하위 디렉터리의 `.gitignore`는 서비스별 로컬 실행에 유용하므로 유지한다.
- 루트 `.gitignore`가 최종 방어선 역할을 하며, 하위 서비스의 캐시와 빌드 결과도 루트에서 제외한다.

### 브랜치 및 merge 전략

- `dev`를 모든 작업의 통합 브랜치로 사용한다.
- `feature/*`, `fix/*`, `docs/*`, `test/*`, `refactor/*`, `chore/*` 브랜치는 Issue 단위로 생성한다.
- 작업 브랜치는 PR을 통해 `dev`에 merge한다.
- 안정화된 `dev`만 release PR로 `main`에 반영한다.

### 리뷰와 문서화

- PR 본문에 요약, 검증, 리뷰 메모, 영향 범위, `Closes #이슈번호`를 포함한다.
- API 계약, 이벤트 흐름, 시나리오, 운영 절차가 바뀌면 `Docs/` 또는 각 서비스의 `Docs/`를 함께 갱신한다.
- 임시 오케스트레이션 로그와 에이전트 상태는 `.hermes/`, `.agents/`, `.codex/`에 둘 수 있으나 Git에는 포함하지 않는다.

### Git 포함 대상

포함한다:

- 서비스 소스 코드와 테스트
- Dockerfile, `docker-compose.yml`, package/requirements 파일
- README, PRD, Docs 문서
- 공개 에셋과 시나리오 데이터

제외한다:

- `.env`, `.secret/`, 키 파일
- `node_modules/`, `dist/`, `build/`, `*.tsbuildinfo`
- `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`
- 세션 저장소와 로컬 DB
- `.hermes/`, `.agents/`, `.codex/`

## 검증 체크

현재 통합 작업에서 확인할 항목:

- `find . -name .git -type d -prune` 결과가 `./.git`만 보여야 한다.
- `git remote -v` 결과가 `origin https://github.com/142spp/asm-team06-ai-study.git`를 보여야 한다.
- `git status --ignored`에서 캐시, 빌드 결과, 비밀 파일이 ignored로 보여야 한다.
- `git branch --show-current` 결과가 `dev`여야 한다.
- 초기 통합 커밋이 `dev`에 존재해야 한다.

## 후속 권장 작업

- GitHub에서 기본 브랜치를 `dev`로 둘지, `main`을 유지하고 PR base만 `dev`로 둘지 팀 규칙을 확정한다.
- GitHub branch protection을 설정해 `dev` 직접 push를 제한하고 PR merge만 허용한다.
- CI가 준비되면 PR 검증에 `AI uv run pytest`, `BE uv run pytest`, `FE npm run build`, `git diff --check`를 연결한다.
