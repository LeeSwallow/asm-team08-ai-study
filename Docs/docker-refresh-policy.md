# Docker Refresh Policy

Purpose: after a BE/FE/AI implementation milestone is validated, the running Docker stack must be rebuilt/recreated so browser/API/integration dogfood tests use the latest code, not stale containers.

## Compose file

Use the root compose file:

```bash
cd /home/min/Projects/Swmaestro/02-AI-SKILL-STUDY/Detective_Agent
docker compose config
```

Current services:

- `ai` -> port `8001`, image `detective-ai-service:local`, context `./AI`
- `backend` -> port `8000`, image `detective-agent-be:local`, context `./BE`, depends on `ai`
- `frontend` -> port `8080`, image `detective-agent-fe:local`, context `./FE`, depends on `backend`

## Required refresh after implementation

When a domain agent reports an implementation milestone done and local validation passes, refresh Docker before accepting dogfood/commit-ready status.

### AI changes

AI changes can affect BE behavior, so rebuild `ai` and recreate `backend` if integration behavior depends on AI responses.

```bash
docker compose build ai
docker compose up -d --no-deps ai
docker compose up -d --no-deps backend
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:8000/api/v1/health
```

### BE changes

BE changes can affect FE proxy/API/SSE behavior, so rebuild `backend`; recreate `frontend` if nginx/proxy config or FE runtime API assumptions changed.

```bash
docker compose build backend
docker compose up -d --no-deps backend
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8080/api/v1/health
```

### FE changes

FE changes require rebuild/recreate `frontend` because Vite static assets are baked into the image.

```bash
docker compose build frontend
docker compose up -d --no-deps frontend
curl -fsS http://127.0.0.1:8080/
```

### Cross-domain or shared contract changes

For schema, endpoint, SSE, proxy, env, Dockerfile, dependency, or compose changes, rebuild the affected dependency chain. When uncertain, rebuild all project services:

```bash
docker compose build ai backend frontend
docker compose up -d ai backend frontend
docker compose ps
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8080/api/v1/health
curl -fsS http://127.0.0.1:8080/
```

## Orchestrator rules

- Do not claim browser/API dogfood reflects latest implementation until the relevant Docker service has been rebuilt/recreated or the agent explicitly proves the running container already includes the change.
- Prefer targeted `docker compose build <service>` and `docker compose up -d --no-deps <service>` for one-service changes.
- Use full-stack rebuild for contract/env/Dockerfile/dependency changes or when integration behavior is stale/uncertain.
- After refresh, verify direct service health plus frontend proxy where relevant.
- Capture logs on failure:

```bash
docker compose ps
docker compose logs --tail=120 ai backend frontend
```

- If Docker refresh fails, mark the milestone as not commit-ready unless the change is docs-only and does not affect runtime.
- Keep generated/vendor files out of commits even if build creates artifacts.

## Agent completion report addition

Each BE/FE/AI completion report must include:

```text
docker refresh:
- required: yes|no
- service(s): ai|backend|frontend|all|none
- reason: code/runtime/docs-only/contract/env/dependency
- suggested commands: ...
- post-refresh checks: ...
```

Docs-only milestones may set `required: no`, but must state why.
