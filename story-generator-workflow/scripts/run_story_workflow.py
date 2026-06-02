#!/usr/bin/env python3
"""Story Generator Workflow CLI.

Usage examples:
  # paste story through stdin and use Hermes/Codex-style local agent loop
  python story-generator-workflow/scripts/run_story_workflow.py \
    --stdin --case-id case_my_story --out story-generator-workflow/out/case_my_story \
    --text-provider hermes --generate-images

  python story-generator-workflow/scripts/run_story_workflow.py \
    --stdin --case-id case_my_story --out story-generator-workflow/out/case_my_story \
    --text-provider codex --generate-images

  # compile an already-approved case JSON into DB + asset prompt artifacts
  python story-generator-workflow/scripts/run_story_workflow.py \
    --case-json BE/data/cases/case_001.json \
    --out story-generator-workflow/out/case_001 --no-generate-images

Default --text-provider is hermes. Use --text-provider codex when you want Codex CLI to run the Writer/Cross-check/Editor roles.
If OPENAI_API_KEY is not set, text-provider=openai fails fast with a clear error.
If --text-provider manual is used, the script writes prompt packets for a human/Hermes/Codex loop without executing agents.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEXT_MODEL = os.getenv("STORYGEN_TEXT_MODEL", "gpt-4.1")
DEFAULT_IMAGE_MODEL = os.getenv("STORYGEN_IMAGE_MODEL", "gpt-image-1")
PRESSURE_STATES = ["low", "medium", "high", "critical"]
FORBIDDEN_PUBLIC_KEY_FRAGMENTS = [
    "secret",
    "solution",
    "isCulprit",
    "hiddenTruth",
    "privateTimeline",
    "privateMotive",
    "actualAction",
    "secretNote",
    "finalVerdict",
]


@dataclass
class WorkflowResult:
    case: dict[str, Any]
    authoring_report: str
    editor_report: dict[str, Any]
    iterations: int


def slugify(value: str, fallback: str = "case") -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣_-]+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value or fallback


def read_story(args: argparse.Namespace) -> str:
    if args.stdin:
        story = sys.stdin.read()
    elif args.story:
        story = Path(args.story).read_text(encoding="utf-8")
    else:
        raise SystemExit("Provide --story <file> or --stdin, unless --case-json is used.")
    story = story.strip()
    if not story:
        raise SystemExit("Story input is empty.")
    return story


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(1))


def openai_chat_json(messages: list[dict[str, str]], model: str, temperature: float = 0.4) -> Any:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --text-provider openai.")
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI chat request failed: HTTP {e.code}: {detail}") from e
    text = payload["choices"][0]["message"]["content"]
    return extract_json(text)


def messages_to_prompt(messages: list[dict[str, str]], role_name: str, output_file: Path | None = None) -> str:
    sections = [
        f"You are running the Story Generator Workflow role: {role_name}.",
        "Return ONLY the requested JSON object. No markdown fences, no commentary.",
    ]
    if output_file is not None:
        sections.append(f"If you use tools or write files, the final JSON must also be saved to: {output_file}")
    for msg in messages:
        sections.append(f"\n[{msg['role'].upper()}]\n{msg['content']}")
    return "\n\n".join(sections)


def run_codex_json(messages: list[dict[str, str]], role_name: str, out_file: Path, model: str | None = None) -> Any:
    if shutil.which("codex") is None:
        raise RuntimeError("codex CLI not found. Install @openai/codex or use --text-provider hermes/openai/manual.")
    prompt_file = out_file.with_suffix(".prompt.txt")
    last_message_file = out_file.with_suffix(".last-message.txt")
    prompt_file.write_text(messages_to_prompt(messages, role_name, out_file), encoding="utf-8")
    cmd = [
        "codex", "exec",
        "--cd", str(Path.cwd()),
        "--sandbox", "workspace-write",
        "--output-last-message", str(last_message_file),
    ]
    if model:
        cmd += ["--model", model]
    cmd += ["-"]
    proc = subprocess.run(cmd, input=prompt_file.read_text(encoding="utf-8"), text=True, capture_output=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"Codex role {role_name} failed with exit {proc.returncode}:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    candidates = []
    if out_file.exists():
        candidates.append(out_file.read_text(encoding="utf-8"))
    if last_message_file.exists():
        candidates.append(last_message_file.read_text(encoding="utf-8"))
    candidates.append(proc.stdout)
    for text in candidates:
        try:
            data = extract_json(text)
            dump_json(out_file, data)
            return data
        except Exception:
            continue
    raise RuntimeError(f"Codex role {role_name} did not return parseable JSON. See {prompt_file} and {last_message_file}.")


def run_hermes_json(messages: list[dict[str, str]], role_name: str, out_file: Path, model: str | None = None) -> Any:
    if shutil.which("hermes") is None:
        raise RuntimeError("hermes CLI not found. Use --text-provider codex/openai/manual.")
    prompt_file = out_file.with_suffix(".prompt.txt")
    prompt_file.write_text(messages_to_prompt(messages, role_name, out_file), encoding="utf-8")
    cmd = ["hermes", "chat", "--query", prompt_file.read_text(encoding="utf-8"), "--quiet", "--source", "story-generator-workflow", "--max-turns", "6"]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"Hermes role {role_name} failed with exit {proc.returncode}:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    candidates = []
    if out_file.exists():
        candidates.append(out_file.read_text(encoding="utf-8"))
    candidates.append(proc.stdout)
    for text in candidates:
        try:
            data = extract_json(text)
            dump_json(out_file, data)
            return data
        except Exception:
            continue
    raise RuntimeError(f"Hermes role {role_name} did not return parseable JSON. See {prompt_file}.")


def run_role_json(messages: list[dict[str, str]], role_name: str, args: argparse.Namespace, out_file: Path, temperature: float = 0.4) -> Any:
    if args.text_provider == "openai":
        data = openai_chat_json(messages, args.text_model, temperature=temperature)
        dump_json(out_file, data)
        return data
    if args.text_provider == "codex":
        return run_codex_json(messages, role_name, out_file, model=args.text_model if args.text_model else None)
    if args.text_provider == "hermes":
        return run_hermes_json(messages, role_name, out_file, model=args.text_model if args.text_model else None)
    raise RuntimeError(f"Unsupported role text provider: {args.text_provider}")


def writer_prompt(story: str, case_id: str, feedback: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    feedback_block = json.dumps(feedback or [], ensure_ascii=False, indent=2)
    system = """
You are the Writer for a Korean noir Detective Agent game. Convert raw story into a playable structured detective case.
Hard rules:
- Return JSON only.
- Do not generate image files.
- Design for gameplay: cross-testimony, evidence puzzles, clue paths, pressure personas, culprit defense arc.
- Separate public story from hidden truth.
- Backend owns final state; AI only proposes dialogue/events later.
- Use stable IDs with prefixes: case_, scene_, char_, ev_, rec_, st_, q_, tl_, ctl_, con_, path_, vis_.
""".strip()
    user = f"""
CASE ID: {case_id}

RAW STORY:
{story}

EDITOR/CROSS-CHECK FEEDBACK TO ADDRESS:
{feedback_block}

Return this JSON object shape:
{{
  "case": {{
    "caseId": "{case_id}",
    "sceneId": "scene_{case_id}",
    "title": "...",
    "summary": "...",
    "victimId": "victim_...",
    "victimName": "...",
    "incidentTime": "...",
    "incidentLocation": "...",
    "questionLimit": 12,
    "opening": {{"hook":"...","objective":"...","rules":[],"victoryCondition":"..."}},
    "storyline": {{
      "publicPremise":"...",
      "acts":[{{"actId":"alibi_collection","title":"...","objective":"...","entryCondition":"session_start","focusSuspectIds":[],"recommendedQuestionIds":[],"requiredClueIds":[],"playerHint":"...","completionCondition":"..."}}],
      "timeline":[{{"timelineId":"tl_...","time":"...","title":"...","description":"...","sourceType":"evidence|statement|record|inference","sourceId":"...","unlockCondition":null,"hidden":false}}],
      "cluePaths":[{{"pathId":"path_...","title":"...","objective":"...","steps":[],"resolvesContradictionId":"con_...","unlocks":[]}}],
      "currentObjectiveRules":[]
    }},
    "suspects": [
      {{
        "id":"char_...","characterId":"char_...","name":"...","role":"...","publicProfile":"...",
        "secret":"private authoring truth; not public","motiveCandidate":true,"isCulprit":false,
        "speechStyle":{{"register":"...","baseTone":"...","vocabulary":[],"avoid":[],"low":{{"tone":"...","sample":"..."}},"medium":{{"tone":"...","sample":"..."}},"high":{{"tone":"...","sample":"..."}},"critical":{{"tone":"...","sample":"..."}}}},
        "defenseArc":{{"low":{{"mode":"...","strategy":"..."}},"medium":{{"mode":"...","strategy":"..."}},"high":{{"mode":"...","strategy":"..."}},"critical":{{"mode":"...","strategy":"..."}}}},
        "publicTimeline":[]
      }}
    ],
    "characterTimelines": [],
    "evidence": [],
    "records": [],
    "relations": [],
    "statements": [],
    "questions": [],
    "contradictions": [],
    "visualProfiles": [],
    "solution": {{"culpritId":"char_...","motive":"...","method":"...","requiredContradictionIds":[],"requiredEvidenceIds":[],"requiredStatementIds":[],"endings":{{}}}}
  }},
  "writerNotes": {{
    "suspectUsefulnessMatrix": [],
    "contradictionRouteMatrix": [],
    "culpritDefenseSummary": "...",
    "assetSeeds": {{"backgrounds":[],"characters":[],"evidence":[]}}
  }}
}}

Minimums: 3-5 suspects, >=8 evidence, >=4 contradictions, every suspect useful, culprit has four pressure-state defense arc.
""".strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def crosscheck_prompt(writer_packet: dict[str, Any]) -> list[dict[str, str]]:
    system = """
You are the Cross-check Writer. Attack the detective case for consistency, solvability, cross-testimony value, and public/private leakage.
Return JSON only. Be concrete and actionable.
""".strip()
    user = f"""
Review this Writer packet:
{json.dumps(writer_packet, ensure_ascii=False, indent=2)}

Return:
{{
  "blockingIssues": [{{"id":"cc_001","severity":"blocker|high|medium|low","issue":"...","requiredFix":"..."}}],
  "suspectUsefulnessMatrix": [{{"suspectId":"...","helpsExpose":"...","exposedBy":"...","roleQuality":"pass|weak|fail"}}],
  "contradictionRouteCoverage": [{{"contradictionId":"...","coverage":"pass|weak|fail","note":"..."}}],
  "timelineConsistency": "pass|weak|fail",
  "publicPrivateLeakageRisk": "pass|weak|fail",
  "summary": "..."
}}
""".strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def editor_prompt(writer_packet: dict[str, Any], crosscheck: dict[str, Any]) -> list[dict[str, str]]:
    system = """
You are the Editor and approval gate for a Detective Agent game case. Approve only if it is fun, fair, and structurally ready.
Return JSON only. Do not approve if cross-testimony, evidence puzzle, or culprit defense is weak.
""".strip()
    user = f"""
Writer packet:
{json.dumps(writer_packet, ensure_ascii=False, indent=2)}

Cross-check report:
{json.dumps(crosscheck, ensure_ascii=False, indent=2)}

Score each 0-3:
- crossTestimony: other suspects' testimony organically helps expose a culprit.
- evidencePuzzle: evidence requires interesting comparison, not one-click answer.
- culpritDefense: culprit has believable pressure-stage defense.
- innocentSuspects: innocent suspects have fair useful false leads/secrets.
- storyFlow: opening -> alibi -> first break -> motive/opportunity -> final accusation flows well.
- fairDifficulty: public clues allow solving.
- runtimeStructure: IDs, gates, contradictions, assets can compile.

Approval rule: total >= 15, crossTestimony >=2, evidencePuzzle >=2, culpritDefense >=2, and no blocker issues.

Return:
{{
  "editorDecision": "approved|revise|blocked",
  "score": {{"crossTestimony":0,"evidencePuzzle":0,"culpritDefense":0,"innocentSuspects":0,"storyFlow":0,"fairDifficulty":0,"runtimeStructure":0}},
  "blockingIssues": [],
  "requiredRevisions": [{{"id":"rev_001","severity":"blocker|high|medium|low","target":"writer|cross_checker","issue":"...","requiredChange":"...","acceptanceCheck":"..."}}],
  "acceptedStrengths": [],
  "assetGate": {{"allowed": false, "reason":"..."}}
}}
""".strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def manual_prompt_packet(story: str, case_id: str, out_dir: Path) -> None:
    ensure_dir(out_dir / "authoring")
    (out_dir / "authoring" / "source_story.md").write_text(story + "\n", encoding="utf-8")
    (out_dir / "authoring" / "writer_prompt.txt").write_text(
        "SYSTEM:\n" + writer_prompt(story, case_id)[0]["content"] + "\n\nUSER:\n" + writer_prompt(story, case_id)[1]["content"] + "\n",
        encoding="utf-8",
    )
    report = """# Manual Story Workflow Packet

`--text-provider manual` was selected. Fill these files in order:

1. Send `authoring/writer_prompt.txt` to Writer and save JSON as `authoring/writer_packet.json`.
2. Send Writer packet through Cross-check prompt from docs/workflow-contract.md and save `authoring/crosscheck_report.json`.
3. Send both through Editor gate from docs/editor-gate.md and save `authoring/editor_report.json`.
4. If approved, rerun this script with `--case-json authoring/writer_packet.case.json` or extract `.case` to `case.json` and run export.
"""
    (out_dir / "authoring_report.md").write_text(report, encoding="utf-8")


def run_authoring_loop(story: str, case_id: str, args: argparse.Namespace, out_dir: Path) -> WorkflowResult:
    if args.text_provider == "manual":
        manual_prompt_packet(story, case_id, out_dir)
        raise SystemExit(f"Manual prompt packet written to {out_dir}. Fill approval outputs, then rerun with --case-json.")
    feedback: list[dict[str, Any]] = []
    authoring_dir = out_dir / "authoring"
    ensure_dir(authoring_dir)
    (authoring_dir / "source_story.md").write_text(story + "\n", encoding="utf-8")
    report_lines = ["# Authoring Report", ""]
    last_writer: dict[str, Any] | None = None
    last_crosscheck: dict[str, Any] | None = None
    last_editor: dict[str, Any] | None = None

    for iteration in range(1, args.max_iterations + 1):
        writer_packet = run_role_json(writer_prompt(story, case_id, feedback), "Writer", args, authoring_dir / f"writer_packet_{iteration}.json", temperature=0.55)
        if "case" not in writer_packet:
            raise RuntimeError("Writer response missing top-level 'case'.")

        crosscheck = run_role_json(crosscheck_prompt(writer_packet), "Cross-check Writer", args, authoring_dir / f"crosscheck_report_{iteration}.json", temperature=0.25)

        editor = run_role_json(editor_prompt(writer_packet, crosscheck), "Editor", args, authoring_dir / f"editor_report_{iteration}.json", temperature=0.1)

        decision = editor.get("editorDecision", "revise")
        report_lines += [f"## Iteration {iteration}", "", f"Decision: `{decision}`", ""]
        report_lines += ["### Cross-check summary", "", str(crosscheck.get("summary", "")), ""]
        for issue in crosscheck.get("blockingIssues", []):
            report_lines.append(f"- cross-check {issue.get('severity')}: {issue.get('issue')} -> {issue.get('requiredFix')}")
        report_lines += ["", "### Editor required revisions", ""]
        for rev in editor.get("requiredRevisions", []):
            report_lines.append(f"- {rev.get('severity')}: {rev.get('issue')} -> {rev.get('requiredChange')}")
        report_lines.append("")

        last_writer, last_crosscheck, last_editor = writer_packet, crosscheck, editor
        if decision == "approved":
            editor.setdefault("assetGate", {})["allowed"] = True
            return WorkflowResult(writer_packet["case"], "\n".join(report_lines), editor, iteration)
        feedback = [
            {"source": "crosscheck", "report": crosscheck},
            {"source": "editor", "report": editor},
        ]

    assert last_writer is not None and last_editor is not None
    if args.allow_unapproved_export:
        report_lines.append("\nWARNING: exported last unapproved draft because --allow-unapproved-export was set.")
        return WorkflowResult(last_writer["case"], "\n".join(report_lines), last_editor, args.max_iterations)
    raise RuntimeError(f"Editor did not approve within {args.max_iterations} iterations. See {authoring_dir}.")


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def cypher_string(value: Any) -> str:
    if value is None:
        return "null"
    return json.dumps(str(value), ensure_ascii=False)


def cypher_bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def cypher_int(value: Any, default: int = 0) -> str:
    try:
        return str(int(value))
    except Exception:
        return str(default)


def write_data_sql(case: dict[str, Any], out_dir: Path) -> Path:
    payload = json.dumps(case, ensure_ascii=False, separators=(",", ":"))
    content = f"""-- Generated by story-generator-workflow/scripts/run_story_workflow.py
-- Idempotent PostgreSQL seed for BE/scripts/init_schema.sql
BEGIN;

INSERT INTO cases (case_id, payload)
VALUES ({sql_literal(case['caseId'])}, {sql_literal(payload)}::jsonb)
ON CONFLICT (case_id) DO UPDATE
SET payload = EXCLUDED.payload;

COMMIT;
"""
    path = out_dir / "data.sql"
    path.write_text(content, encoding="utf-8")
    return path


def write_neo4j_cypher(case: dict[str, Any], out_dir: Path) -> Path:
    cid = case["caseId"]
    lines = [
        "// Generated by story-generator-workflow/scripts/run_story_workflow.py",
        f"MATCH (n {{caseId: {cypher_string(cid)}}}) DETACH DELETE n;",
        "",
        "CREATE (c:Case {",
        f"  caseId: {cypher_string(cid)},",
        f"  sceneId: {cypher_string(case.get('sceneId',''))},",
        f"  title: {cypher_string(case.get('title',''))},",
        f"  summary: {cypher_string(case.get('summary',''))},",
        f"  victimId: {cypher_string(case.get('victimId',''))},",
        f"  victimName: {cypher_string(case.get('victimName',''))},",
        f"  incidentTime: {cypher_string(case.get('incidentTime',''))},",
        f"  incidentLocation: {cypher_string(case.get('incidentLocation',''))},",
        f"  questionLimit: {cypher_int(case.get('questionLimit', 12), 12)}",
        "});",
        "",
    ]

    def create_node(label: str, var: str, props: dict[str, Any], rel: str) -> None:
        prop_parts = [f"caseId: {cypher_string(cid)}"]
        for k, v in props.items():
            if isinstance(v, bool):
                prop_parts.append(f"{k}: {cypher_bool(v)}")
            elif isinstance(v, int):
                prop_parts.append(f"{k}: {v}")
            else:
                prop_parts.append(f"{k}: {cypher_string(v)}")
        lines.append(f"CREATE ({var}:{label} {{{', '.join(prop_parts)}}});")
        lines.append(f"MATCH (c:Case {{caseId: {cypher_string(cid)}}}), ({var}:{label} {{caseId: {cypher_string(cid)}, {next(iter(props.keys()))}: {cypher_string(next(iter(props.values())))}}}) CREATE (c)-[:{rel}]->({var});")

    for i, s in enumerate(case.get("suspects", []), 1):
        create_node("Character", f"ch{i}", {
            "characterId": s.get("characterId") or s.get("id"),
            "name": s.get("name", ""),
            "role": s.get("role", ""),
            "publicPersona": s.get("publicProfile", ""),
            "isCulprit": bool(s.get("isCulprit", False)),
            "secret": s.get("secret", ""),
            "speechStyle": json.dumps(s.get("speechStyle", {}), ensure_ascii=False),
            "defenseArc": json.dumps(s.get("defenseArc", {}), ensure_ascii=False),
        }, "HAS_CHARACTER")
    for i, ev in enumerate(case.get("evidence", []), 1):
        create_node("Evidence", f"ev{i}", {
            "evidenceId": ev.get("id"), "name": ev.get("name", ""), "type": ev.get("type", ""),
            "description": ev.get("description", ""), "foundAt": ev.get("foundAt", ""),
            "timeWindow": ev.get("timeWindow", ""), "initiallyVisible": bool(ev.get("initiallyVisible", True)),
            "unlockCondition": ev.get("unlockCondition", ""),
        }, "HAS_EVIDENCE")
    for i, rec in enumerate(case.get("records", []), 1):
        create_node("Record", f"rec{i}", {
            "recordId": rec.get("id"), "name": rec.get("name", ""), "description": rec.get("description", ""),
            "timeWindow": rec.get("timeWindow", ""), "initiallyVisible": bool(rec.get("initiallyVisible", True)),
        }, "HAS_RECORD")
    for i, st in enumerate(case.get("statements", []), 1):
        create_node("Statement", f"st{i}", {
            "statementId": st.get("id"), "characterId": st.get("characterId", ""), "text": st.get("text", ""),
            "questionText": st.get("questionText", ""), "timeWindow": st.get("timeWindow", ""),
            "location": st.get("location", ""), "initiallyVisible": bool(st.get("initiallyVisible", True)),
            "unlockCondition": st.get("unlockCondition", ""),
        }, "HAS_STATEMENT")
        if st.get("characterId"):
            lines.append(f"MATCH (ch:Character {{caseId: {cypher_string(cid)}, characterId: {cypher_string(st.get('characterId'))}}}), (s:Statement {{caseId: {cypher_string(cid)}, statementId: {cypher_string(st.get('id'))}}}) MERGE (ch)-[:MADE_STATEMENT]->(s);")
    for i, q in enumerate(case.get("questions", []), 1):
        create_node("Question", f"q{i}", {
            "questionId": q.get("id"), "characterId": q.get("characterId", ""), "text": q.get("text", ""),
            "answer": q.get("answer", ""), "initiallyUnlocked": bool(q.get("initiallyUnlocked", True)),
            "unlockCondition": q.get("unlockCondition", ""),
        }, "HAS_QUESTION")
        if q.get("characterId"):
            lines.append(f"MATCH (ch:Character {{caseId: {cypher_string(cid)}, characterId: {cypher_string(q.get('characterId'))}}}), (q:Question {{caseId: {cypher_string(cid)}, questionId: {cypher_string(q.get('id'))}}}) MERGE (ch)-[:HAS_QUESTION]->(q);")
    for i, con in enumerate(case.get("contradictions", []), 1):
        create_node("Contradiction", f"con{i}", {
            "contradictionId": con.get("id"), "title": con.get("title", ""), "message": con.get("message", ""),
            "reasonCode": con.get("reasonCode", ""), "severity": con.get("severity", ""),
            "pressureDelta": int(con.get("pressureDelta", 0) or 0), "suspectId": con.get("suspectId", ""),
        }, "HAS_CONTRADICTION")
        if con.get("suspectId"):
            lines.append(f"MATCH (con:Contradiction {{caseId: {cypher_string(cid)}, contradictionId: {cypher_string(con.get('id'))}}}), (ch:Character {{caseId: {cypher_string(cid)}, characterId: {cypher_string(con.get('suspectId'))}}}) MERGE (con)-[:ABOUT]->(ch);")
        for sid in con.get("requiredStatementIds", []):
            lines.append(f"MATCH (con:Contradiction {{caseId: {cypher_string(cid)}, contradictionId: {cypher_string(con.get('id'))}}}), (s:Statement {{caseId: {cypher_string(cid)}, statementId: {cypher_string(sid)}}}) MERGE (con)-[:REQUIRES_STATEMENT]->(s);")
        for eid in con.get("requiredEvidenceIds", []):
            lines.append(f"MATCH (con:Contradiction {{caseId: {cypher_string(cid)}, contradictionId: {cypher_string(con.get('id'))}}}), (e:Evidence {{caseId: {cypher_string(cid)}, evidenceId: {cypher_string(eid)}}}) MERGE (con)-[:REQUIRES_EVIDENCE]->(e);")
    for i, tl in enumerate(case.get("storyline", {}).get("timeline", []), 1):
        create_node("TimelineEvent", f"tl{i}", {
            "timelineId": tl.get("timelineId"), "time": tl.get("time", ""), "title": tl.get("title", ""),
            "description": tl.get("description", ""), "sourceType": tl.get("sourceType", ""),
            "sourceId": tl.get("sourceId", ""), "hidden": bool(tl.get("hidden", False)),
            "unlockCondition": tl.get("unlockCondition", ""),
        }, "HAS_TIMELINE_EVENT")
    sol = case.get("solution", {})
    lines += [
        "",
        f"CREATE (sol:Solution {{caseId: {cypher_string(cid)}, culpritId: {cypher_string(sol.get('culpritId',''))}, motive: {cypher_string(sol.get('motive',''))}, method: {cypher_string(sol.get('method',''))}, requiredContradictionIds: {cypher_string(json.dumps(sol.get('requiredContradictionIds', []), ensure_ascii=False))}, requiredEvidenceIds: {cypher_string(json.dumps(sol.get('requiredEvidenceIds', []), ensure_ascii=False))}, requiredStatementIds: {cypher_string(json.dumps(sol.get('requiredStatementIds', []), ensure_ascii=False))}}});",
        f"MATCH (c:Case {{caseId: {cypher_string(cid)}}}), (sol:Solution {{caseId: {cypher_string(cid)}}}) CREATE (c)-[:HAS_SOLUTION]->(sol);",
        "",
    ]
    path = out_dir / "neo4j.cypher"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_asset_manifest(case: dict[str, Any]) -> dict[str, Any]:
    cid = case["caseId"]
    style = {
        "genre": "Korean noir detective visual novel",
        "palette": ["deep navy", "warm amber", "desaturated burgundy", "charcoal black"],
        "lighting": "cinematic noir rim light, rainy mansion atmosphere",
        "negativePrompt": "text, watermark, logo, low quality, distorted face, childish cartoon, placeholder svg, ugly portrait",
    }
    assets: list[dict[str, Any]] = []
    location = case.get("incidentLocation", "mystery crime scene")
    assets.append({
        "assetId": f"vis_{cid}_background_main",
        "type": "background",
        "prompt": f"Cinematic Korean noir detective game background, {location}, dark rainy atmosphere, evidence board mood, premium visual novel web game, deep navy and warm amber palette, no people, no text, highly detailed.",
        "outputPath": "assets/backgrounds/main.png",
    })
    for suspect in case.get("suspects", []):
        char_id = suspect.get("characterId") or suspect.get("id")
        name = suspect.get("name", char_id)
        role = suspect.get("role", "suspect")
        profile = suspect.get("publicProfile", "")
        for pressure in PRESSURE_STATES:
            style_part = suspect.get("speechStyle", {}).get(pressure, {})
            expression = style_part.get("tone") or {
                "low": "controlled neutral mask",
                "medium": "defensive guarded expression",
                "high": "rattled pressured expression",
                "critical": "broken exposed expression",
            }[pressure]
            assets.append({
                "assetId": f"vis_{char_id}_{pressure}",
                "type": "suspect_portrait",
                "characterId": char_id,
                "pressure": pressure,
                "expression": expression,
                "prompt": f"Korean noir detective visual novel suspect portrait, {name}, {role}, {profile}. Pressure state: {pressure}, expression: {expression}. Consistent identity, centered bust portrait, dark mansion rim light, semi-realistic high quality illustration, readable emotion, no text, no watermark.",
                "outputPath": f"assets/characters/{char_id}/{pressure}.png",
            })
    for ev in case.get("evidence", []):
        ev_id = ev.get("id")
        assets.append({
            "assetId": f"vis_{ev_id}",
            "type": "evidence_photo",
            "evidenceId": ev_id,
            "prompt": f"Noir detective evidence photo, close-up of {ev.get('name','evidence')}, {ev.get('description','')}. Found at {ev.get('foundAt','crime scene')}. Premium game evidence thumbnail, dark tabletop, realistic prop, no readable text unless generic, no watermark.",
            "outputPath": f"assets/evidence/{ev_id}.png",
        })
    return {"caseId": cid, "styleBible": style, "assets": assets}


def attach_visual_profiles(case: dict[str, Any], manifest: dict[str, Any]) -> None:
    profiles = []
    for suspect in case.get("suspects", []):
        char_id = suspect.get("characterId") or suspect.get("id")
        profiles.append({
            "characterId": char_id,
            "states": {
                p: {"assetId": f"vis_{char_id}_{p}", "expression": p}
                for p in PRESSURE_STATES
            },
        })
    case["visualProfiles"] = profiles
    case.setdefault("visualAssets", {})["manifestPath"] = "asset_manifest.json"


def openai_generate_image(prompt: str, output_path: Path, model: str) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --generate-images with --image-provider openai.")
    body = {"model": model, "prompt": prompt, "size": "1024x1024"}
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as res:
        payload = json.loads(res.read().decode("utf-8"))
    item = payload["data"][0]
    ensure_dir(output_path.parent)
    if "b64_json" in item:
        output_path.write_bytes(base64.b64decode(item["b64_json"]))
    elif "url" in item:
        with urllib.request.urlopen(item["url"], timeout=300) as img_res:
            output_path.write_bytes(img_res.read())
    else:
        raise RuntimeError("Image response did not include b64_json or url.")


def write_asset_outputs(manifest: dict[str, Any], out_dir: Path, generate: bool, image_provider: str, image_model: str, limit: int | None) -> None:
    dump_json(out_dir / "asset_manifest.json", manifest)
    prompt_dir = out_dir / "asset_prompts"
    ensure_dir(prompt_dir)
    assets = manifest.get("assets", [])
    for asset in assets:
        prompt_path = prompt_dir / f"{asset['assetId']}.txt"
        prompt_path.write_text(asset["prompt"] + "\n\nNEGATIVE: " + manifest["styleBible"]["negativePrompt"] + "\n", encoding="utf-8")
    if not generate:
        return
    if image_provider != "openai":
        raise RuntimeError(f"Unsupported image provider: {image_provider}")
    selected = assets[:limit] if limit else assets
    for idx, asset in enumerate(selected, 1):
        output_path = out_dir / asset["outputPath"]
        print(f"[image {idx}/{len(selected)}] {asset['assetId']} -> {output_path}")
        openai_generate_image(asset["prompt"] + " Negative prompt: " + manifest["styleBible"]["negativePrompt"], output_path, image_model)
        time.sleep(0.5)


def validate_case(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["caseId", "sceneId", "title", "summary", "suspects", "evidence", "statements", "questions", "contradictions", "opening", "storyline", "solution"]
    for key in required:
        if key not in case:
            errors.append(f"missing top-level key: {key}")
    ids: set[str] = set()
    for section in ["suspects", "evidence", "records", "statements", "questions", "contradictions"]:
        for item in case.get(section, []):
            if item.get("id"):
                if item["id"] in ids:
                    errors.append(f"duplicate id: {item['id']}")
                ids.add(item["id"])
            if section == "suspects" and item.get("characterId"):
                ids.add(item["characterId"])
    for tl in case.get("storyline", {}).get("timeline", []):
        if tl.get("timelineId"):
            ids.add(tl["timelineId"])
    for ctl in case.get("characterTimelines", []):
        for key in ["publicClaims", "perceivedEvents", "privateEvents"]:
            for item in ctl.get(key, []):
                if item.get("timelineId"):
                    ids.add(item["timelineId"])
    for con in case.get("contradictions", []):
        for ref_key in ["suspectId", "requiredStatementIds", "requiredEvidenceIds", "requiredTimelineIds", "unlocksEvidenceIds", "unlocksQuestionIds", "unlocksStatementIds"]:
            refs = con.get(ref_key, [])
            if isinstance(refs, str):
                refs = [refs]
            for ref in refs:
                if ref and ref not in ids:
                    errors.append(f"unresolved ref in {con.get('id')}.{ref_key}: {ref}")
    for s in case.get("suspects", []):
        style = s.get("speechStyle", {})
        missing_states = [p for p in PRESSURE_STATES if p not in style and not any(p in v.get("tensionLevels", []) for v in s.get("personaVariants", []))]
        if missing_states:
            errors.append(f"{s.get('characterId') or s.get('id')} missing pressure speech/persona states: {missing_states}")
    return errors


def export_case_package(case: dict[str, Any], out_dir: Path, args: argparse.Namespace, authoring_report: str = "", editor_report: dict[str, Any] | None = None) -> None:
    ensure_dir(out_dir)
    manifest = build_asset_manifest(case)
    attach_visual_profiles(case, manifest)
    errors = validate_case(case)
    if errors:
        dump_json(out_dir / "validation_errors.json", errors)
        if not args.allow_invalid_export:
            raise RuntimeError("Case validation failed:\n- " + "\n- ".join(errors))
    dump_json(out_dir / "case.json", case)
    write_data_sql(case, out_dir)
    write_neo4j_cypher(case, out_dir)
    write_asset_outputs(manifest, out_dir, args.generate_images, args.image_provider, args.image_model, args.image_limit)
    if authoring_report:
        (out_dir / "authoring_report.md").write_text(authoring_report, encoding="utf-8")
    if editor_report is not None:
        dump_json(out_dir / "editor_report.json", editor_report)
    summary = {
        "caseId": case.get("caseId"),
        "outDir": str(out_dir),
        "files": ["case.json", "data.sql", "neo4j.cypher", "asset_manifest.json", "asset_prompts/"],
        "assets": len(manifest.get("assets", [])),
        "validationErrors": errors,
        "imagesGenerated": bool(args.generate_images),
    }
    dump_json(out_dir / "workflow_summary.json", summary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Detective Agent case package from pasted story or approved case JSON.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--story", help="Path to raw source story markdown/text")
    src.add_argument("--stdin", action="store_true", help="Read raw source story from stdin")
    src.add_argument("--case-json", help="Skip authoring loop and compile this approved case JSON")
    parser.add_argument("--case-id", default=None, help="Stable case_id to use for new story. Defaults to case_<slug>.")
    parser.add_argument("--out", default=None, help="Output directory. Defaults to story-generator-workflow/out/<case-id>")
    parser.add_argument("--text-provider", choices=["hermes", "codex", "openai", "manual"], default="hermes", help="Agent/model runner for Writer/Cross-check/Editor. hermes/codex use local agent CLIs; openai uses direct API; manual writes prompt packets.")
    parser.add_argument("--text-model", default=DEFAULT_TEXT_MODEL)
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--allow-unapproved-export", action="store_true", help="Export last draft even without Editor approval. Not recommended.")
    parser.add_argument("--allow-invalid-export", action="store_true", help="Write artifacts even if local structural validation fails.")
    parser.add_argument("--generate-images", action="store_true", help="Generate image files from asset manifest after approval/export.")
    parser.add_argument("--no-generate-images", dest="generate_images", action="store_false")
    parser.set_defaults(generate_images=False)
    parser.add_argument("--image-provider", choices=["openai"], default="openai")
    parser.add_argument("--image-model", default=DEFAULT_IMAGE_MODEL)
    parser.add_argument("--image-limit", type=int, default=None, help="Limit generated image count for smoke tests.")
    args = parser.parse_args()

    if args.case_json:
        case = json.loads(Path(args.case_json).read_text(encoding="utf-8"))
        case_id = case.get("caseId") or args.case_id or "case_import"
        out_dir = Path(args.out) if args.out else ROOT / "out" / case_id
        export_case_package(case, out_dir, args, authoring_report="# Imported approved case JSON\n", editor_report={"editorDecision": "imported"})
        print(f"OK: exported case package to {out_dir}")
        return 0

    story = read_story(args)
    case_id = args.case_id or "case_" + slugify(story[:40], "story")
    if not case_id.startswith("case_"):
        case_id = "case_" + case_id
    out_dir = Path(args.out) if args.out else ROOT / "out" / case_id
    ensure_dir(out_dir)
    result = run_authoring_loop(story, case_id, args, out_dir)
    export_case_package(result.case, out_dir, args, result.authoring_report, result.editor_report)
    print(f"OK: editor approved after {result.iterations} iteration(s); exported case package to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
