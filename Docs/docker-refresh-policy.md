# Docker Refresh 정책

목적: BE/FE 구현 마일스톤이 검증된 후, 브라우저/API/통합 dogfood 테스트가 최신 코드를 사용할 수 있도록 Docker 스택을 재빌드/재실행해야 한다.

## Compose 파일

루트 compose 파일 사용:

```bash
cd /home/min/Projects/Swmaestro/02-AI-SKILL-STUDY/Detective_Agent
docker compose config
```

현재 서비스:

- `backend` → 포트 `8000`, 이미지 `detective-agent-be:local`, 컨텍스트 `./BE`
  - AI 엔진(`app/ai_engine/`) 포함: CharacterAgent → LightRuleCheck → GameMasterAgent
- `frontend` → 포트 `8080`, 이미지 `detective-agent-fe:local`, 컨텍스트 `./FE`, `backend` 의존

## 구현 후 필수 refresh

도메인 에이전트가 구현 마일스톤 완료를 보고하고 로컬 검증이 통과되면, dogfood/commit-ready 상태를 수락하기 전에 Docker를 refresh한다.

### BE 변경 (AI 엔진 포함)

BE 변경은 FE 프록시/API/SSE 동작에 영향을 줄 수 있으므로 `backend`를 재빌드한다. nginx/프록시 설정 또는 FE 런타임 API 가정이 변경된 경우 `frontend`도 재실행한다.

```bash
docker compose build backend
docker compose up -d --no-deps backend
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8080/api/v1/health
```

### FE 변경

FE 변경은 Vite 정적 에셋이 이미지에 포함되므로 `frontend` 재빌드/재실행이 필요하다.

```bash
docker compose build frontend
docker compose up -d --no-deps frontend
curl -fsS http://127.0.0.1:8080/
```

### 크로스 도메인 또는 공유 계약 변경

스키마, 엔드포인트, SSE, 프록시, 환경 변수, Dockerfile, 의존성, compose 변경의 경우 영향을 받는 의존 체인을 재빌드한다. 불확실한 경우 모든 프로젝트 서비스를 재빌드한다.

```bash
docker compose build backend frontend
docker compose up -d backend frontend
docker compose ps
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8080/api/v1/health
curl -fsS http://127.0.0.1:8080/
```

## 오케스트레이터 규칙

- 관련 Docker 서비스가 재빌드/재실행되거나 에이전트가 실행 중인 컨테이너에 변경이 포함됨을 명시적으로 증명하기 전까지 브라우저/API dogfood가 최신 구현을 반영한다고 주장하지 않는다.
- 단일 서비스 변경에는 `docker compose build <service>`와 `docker compose up -d --no-deps <service>`를 선호한다.
- 계약/환경 변수/Dockerfile/의존성 변경이나 통합 동작이 오래됐거나 불확실한 경우 전체 스택 재빌드를 사용한다.
- Refresh 후 서비스 헬스와 관련된 프론트엔드 프록시를 직접 확인한다.
- 실패 시 로그 확인:

```bash
docker compose ps
docker compose logs --tail=120 backend frontend
```

- Docker refresh가 실패하면 변경이 docs-only이고 런타임에 영향이 없는 경우가 아니면 마일스톤을 commit-ready 아님으로 표시한다.
- 빌드가 생성한 아티팩트가 있어도 생성된/벤더 파일은 커밋에 포함하지 않는다.

## 에이전트 완료 보고 추가 항목

각 BE/FE 완료 보고에 반드시 포함:

```text
docker refresh:
- 필요 여부: yes|no
- 서비스: backend|frontend|all|none
- 이유: code/runtime/docs-only/contract/env/dependency
- 권장 명령:
- refresh 후 확인 항목:
```

docs-only 마일스톤은 `필요 여부: no`로 설정할 수 있으나 이유를 명시해야 한다.
