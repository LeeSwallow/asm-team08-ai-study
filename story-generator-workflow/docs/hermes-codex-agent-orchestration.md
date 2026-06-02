# Hermes / Codex Agent Orchestration

이 workflow는 단순 API 호출 스크립트가 아니라 Hermes 또는 Codex가 역할 에이전트로 참여하는 구조를 기본값으로 둔다.

## 1. Role Mapping

| Workflow role | Hermes/Codex execution meaning | Output |
| --- | --- | --- |
| Writer | 원천 스토리를 Detective Agent 케이스 설계로 변환하는 창작 에이전트 | `authoring/writer_packet_N.json` |
| Cross-check Writer | Writer 산출물을 공격적으로 검증하는 반대 작가/논리 검증 에이전트 | `authoring/crosscheck_report_N.json` |
| Editor | 게임성, 스토리 흐름, 성립성, 런타임 구조성을 점수화하고 승인/수정/차단 결정 | `authoring/editor_report_N.json` |
| Compiler | 승인된 `.case`를 DB/Asset 산출물로 컴파일하는 deterministic Python 코드 | `case.json`, `data.sql`, `neo4j.cypher`, `asset_manifest.json` |
| Asset Producer | Editor 승인 후 asset prompt 또는 실제 이미지 생성 실행 | `asset_prompts/*.txt`, `assets/**/*.png` |

## 2. Default execution

기본 실행은 Hermes CLI다.

```bash
python story-generator-workflow/scripts/run_story_workflow.py \
  --stdin \
  --case-id case_pasted_story \
  --out story-generator-workflow/out/case_pasted_story \
  --text-provider hermes
```

Codex를 role runner로 쓰려면:

```bash
python story-generator-workflow/scripts/run_story_workflow.py \
  --stdin \
  --case-id case_pasted_story \
  --out story-generator-workflow/out/case_pasted_story \
  --text-provider codex
```

이미지까지 실제 생성하려면 `--generate-images`를 붙인다. 현재 실제 이미지 생성 provider는 OpenAI Images API이며, Hermes/Codex는 image prompt/manifest 설계와 승인 루프를 담당한다.

## 3. Why not one giant prompt?

한 번에 “스토리 만들어줘 + DB 만들어줘 + 이미지 만들어줘”를 호출하면 다음 문제가 생긴다.

- 편집자 승인 전 에셋을 만들어 버려 asset/story mismatch 발생
- 용의자 간 교차증언이 약한데도 구조가 확정됨
- hidden truth가 public payload로 새기 쉬움
- DB reference/id 오류가 사람이 보기 전까지 누적됨

따라서 에이전트 역할을 분리한다.

```text
Writer creates playable draft
Cross-check attacks draft
Editor decides approve/revise/blocked
Compiler only runs after approval
Assets only run after approval
```

## 4. Agent output discipline

Hermes/Codex role agents는 JSON만 반환해야 한다. 스크립트는 각 role prompt와 final response를 `authoring/`에 저장한다.

- `writer_packet_N.prompt.txt`
- `writer_packet_N.json`
- `crosscheck_report_N.prompt.txt`
- `crosscheck_report_N.json`
- `editor_report_N.prompt.txt`
- `editor_report_N.json`

Codex 실행 시 `--output-last-message`를 사용해서 마지막 응답을 별도 파일로 저장하고 JSON을 추출한다.
Hermes 실행 시 `hermes chat --query ... --quiet --source story-generator-workflow`를 사용한다.

## 5. Human-in-the-loop / manual mode

에이전트 실행 대신 프롬프트만 만들고 싶으면:

```bash
python story-generator-workflow/scripts/run_story_workflow.py \
  --story /tmp/story.md \
  --case-id case_manual \
  --out story-generator-workflow/out/case_manual \
  --text-provider manual
```

이 모드는 `authoring/writer_prompt.txt`를 만들고 멈춘다. 이후 사용자가 Hermes/Codex/tmux pane에 직접 붙여넣어도 된다.

## 6. Non-agent deterministic compiler boundary

다음은 LLM이 아니라 Python 코드가 수행한다.

- ID/reference validation
- `case.json` 쓰기
- PostgreSQL `data.sql` 생성
- Neo4j `neo4j.cypher` 생성
- asset manifest/prompt 파일 생성
- validation summary 생성

즉, Hermes/Codex는 창작/검토/편집 판단을 담당하고, DB/파일 출력은 deterministic compiler가 담당한다.
