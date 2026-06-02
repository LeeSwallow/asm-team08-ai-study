# Story Generator Workflow

목표: 사용자가 원천 스토리를 제공하면 곧바로 케이스를 확정하지 않고, 작가 → 교차검증 작가 → 편집자 승인 루프를 통과한 뒤에만 Detective Agent 런타임용 case JSON, Neo4j Cypher, PostgreSQL data.sql, 배경/인물/증거 에셋 프롬프트와 생성 작업을 산출한다.

핵심 원칙:
1. 스토리는 바로 DB가 되지 않는다. 먼저 게임성 있는 추리 구조로 재설계한다.
2. 편집자가 승인하기 전에는 에셋을 만들지 않는다. 미승인 스토리의 인물/증거 이미지는 낭비이자 불일치 원인이다.
3. LLM은 창작/검토/제안 역할만 한다. 범인, 핵심 수법, 증거 진실, 공개/비공개 경계, DB 상태 권한은 구조화된 산출물과 검증기가 지킨다.
4. 게임성 판단은 “멋진 이야기”보다 “플레이어가 증언과 증거를 유기적으로 대조해 범행을 밝혀낼 수 있는가”를 우선한다.

상위 플로우:

```text
user story
  -> 00_ingest/source_story.md
  -> Writer: case pitch + hidden truth + suspect web + clue paths
  -> Cross-check Writer: contradiction graph, timeline consistency, suspect testimony usefulness review
  -> Editor: game fun / story flow / solvability / asset readiness gate
  -> if rejected: Writer revises using explicit feedback
  -> if accepted: compile structured case package
  -> validate public/private boundary + ID links + contradiction route
  -> generate DB artifacts: case JSON, Neo4j Cypher, PostgreSQL data.sql
  -> generate asset spec: backgrounds, suspect pressure variants, evidence photos
  -> optional image generation provider execution
```

디렉터리 구조:

```text
story-generator-workflow/
  README.md
  SKILL.md
  docs/
    workflow-contract.md
    editor-gate.md
    output-schema.md
    asset-generation-contract.md
    db-export-contract.md
    hermes-codex-agent-orchestration.md
  templates/
    source-story.md
    generation-brief.yaml
    editor-report.yaml
    asset-manifest.yaml
  scripts/
    run_story_workflow.py      # 붙여넣은 스토리 → 승인 루프 → case/db/asset 산출
    validate_story_package.py
```

## 바로 쓰는 방법

### 1) 스토리 붙여넣어서 전체 플로우 실행

```bash
cat > /tmp/my_story.md
# 여기에 원천 스토리 붙여넣기 후 Ctrl-D

python story-generator-workflow/scripts/run_story_workflow.py \
  --story /tmp/my_story.md \
  --case-id case_my_story \
  --out story-generator-workflow/out/case_my_story \
  --text-provider hermes \
  --generate-images
```

동작:
1. Writer가 사건 구조 초안 생성
2. Cross-check Writer가 시간축/증거/교차증언/누설 위험 검토
3. Editor가 게임성/스토리 흐름/성립성 점수화
4. Editor가 `approved`할 때까지 최대 `--max-iterations` 반복
5. 승인되면 다음 파일 생성
   - `case.json`
   - `data.sql`
   - `neo4j.cypher`
   - `asset_manifest.json`
   - `asset_prompts/*.txt`
   - `assets/**.png` (`--generate-images` 사용 시)

### 2) 터미널에서 바로 붙여넣기

```bash
python story-generator-workflow/scripts/run_story_workflow.py \
  --stdin \
  --case-id case_pasted_story \
  --out story-generator-workflow/out/case_pasted_story \
  --text-provider hermes \
  --generate-images

# Codex CLI를 role runner로 쓰려면 --text-provider codex 사용
```

명령 실행 후 스토리를 붙여넣고 Ctrl-D를 누르면 된다.

### 3) 이미 승인된 case JSON만 DB/Asset 산출물로 컴파일

```bash
python story-generator-workflow/scripts/run_story_workflow.py \
  --case-json BE/data/cases/case_001.json \
  --out story-generator-workflow/out/case_001 \
  --no-generate-images
```

이미지 파일을 실제 생성하지 않아도 `asset_manifest.json`과 개별 prompt 파일은 항상 생성된다.

참고: 전체 설계는 Hermes/Codex가 Writer, Cross-check Writer, Editor 역할을 수행하고 Python compiler가 승인된 산출물을 DB/Asset artifact로 변환하는 구조다. 자세한 내용은 `docs/hermes-codex-agent-orchestration.md`를 본다.

### 4) LLM 없이 수동 authoring packet만 만들기

```bash
python story-generator-workflow/scripts/run_story_workflow.py \
  --story /tmp/my_story.md \
  --case-id case_manual \
  --out story-generator-workflow/out/case_manual \
  --text-provider manual
```

이 모드는 `authoring/writer_prompt.txt`를 만들고 멈춘다. 외부/수동 작가-검토-편집 루프에 사용할 수 있다.

Detective Agent 기존 구조와 연결:
- Runtime case JSON: `BE/data/cases/<case_id>.json`
- Neo4j graph import: 기존 `BE/scripts/migrate_case_to_neo4j.py` 또는 생성된 Cypher
- PostgreSQL runtime seed: `BE/scripts/init_schema.sql` 이후 `cases.payload`에 JSONB insert하는 `data.sql`
- 공개/비공개 규칙: `Docs/story-data-contract.md`, `Docs/story-knowledge-wiki-contract.md`, `Docs/db-domain-diagrams.md` 기준
- AI 런타임 경계: CharacterAgent → LightRuleCheck → GameMasterAgent, BE EventProcessor가 proposedEvents 검증

최종 산출물:
1. `case_package/case.json` — BE 런타임용 케이스 데이터
2. `case_package/neo4j.cypher` — 케이스 그래프 seed
3. `case_package/data.sql` — PostgreSQL `cases` seed 및 필요 시 초기 세션/이벤트 seed
4. `case_package/authoring_report.md` — 작가/교차검증/편집자 루프 로그
5. `case_package/asset_manifest.json` — 배경, 용의자 압박도별 이미지, 증거 사진 목록
6. `case_package/assets/` — 생성된 이미지 파일 또는 provider URL 매핑

승인 전 필수 질문:
- 이 케이스의 플레이어 목표가 한 문장으로 명확한가?
- 각 용의자의 증언이 최소 하나 이상의 다른 용의자/증거/타임라인과 연결되는가?
- 범인이 방어할 논리가 단계별로 설계되어 있고, 압박도별로 변하는가?
- 무고한 용의자도 단순 들러리가 아니라 false lead/innocent secret/교차증언 역할을 갖는가?
- 핵심 모순은 최소 3단계 이상으로 해금되어 너무 쉽거나 너무 불가능하지 않은가?
- 공개 payload에 hidden truth, isCulprit, privateTimeline, secretNote가 새지 않는가?
