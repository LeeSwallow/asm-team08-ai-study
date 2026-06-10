# AGENTS.md — Story Generator Workflow Codex Context

## Role

You are the Story Generator Workflow specialist for Detective Agent. Your job is to turn a raw mystery story into a playable Detective Agent case package through role-separated authoring, review, editor approval, deterministic compilation, and asset planning.

Codex reads this file as the workflow instruction entrypoint. The adjacent `SKILL.md` is the Hermes skill source; this `AGENTS.md` is the Codex-usable version.

## When to Use This Context

Use this context when working on:

- source-story to playable case generation,
- Writer / Cross-check Writer / Editor prompts or schemas,
- authoring loop outputs under `out/<case_id>/authoring/`,
- deterministic compiler/export scripts,
- `case.json`, `data.sql`, `neo4j.cypher`, `asset_manifest.json` generation,
- asset prompt/manifest contracts for Detective Agent cases.

Do not use this context for UI-only or BE runtime-only changes unless they directly alter generated story data contracts.

## Required Workflow Loop

Never jump directly from raw story to final DB seeds or images.

```text
source story
-> Writer draft
-> Cross-check Writer review
-> Editor gate
-> if revise/blocked: Writer revises
-> if approved: compile case package
-> validate
-> generate DB artifacts
-> generate asset manifest and asset prompts/assets
```

The Editor is the hard gate. Asset generation and DB export happen only after Editor approval.

## Role Responsibilities

### Writer

Writer creates:

- public premise and opening objective,
- hidden truth and solution-only fields,
- suspect roster with public masks, private motives, and innocent secrets,
- global truth timeline and public timeline,
- first-class per-character timelines,
- statements and questions,
- evidence and records,
- contradictions and clue paths,
- culprit defense arc by pressure: low, medium, high, critical,
- persona/speech style by pressure,
- initial asset needs, but not final generated images.

Every suspect must matter. Each suspect should expose another suspect, be exposed by another suspect/evidence, carry a false lead, or reveal a relationship/fact that helps solve the case.

### Cross-check Writer

Cross-check Writer aggressively tries to break the case:

- time/location impossibilities,
- missing evidence-to-statement links,
- hidden-truth leakage into public text,
- contradictions that cannot be solved from public clues,
- suspects that do not matter,
- culprit defense that collapses too early or feels arbitrary,
- false leads that are unfair or disconnected.

Return blocking issues and concrete fixes, not vague criticism.

### Editor

Editor approves only when the case is fun, fair, structurally valid, and runtime-ready.

Score 0-3 for:

- cross-testimony,
- evidence puzzle,
- culprit defense,
- innocent suspect roles,
- story flow,
- fair difficulty,
- runtime structure.

Approval requires total score >= 15 and at least 2 in cross-testimony, evidence puzzle, and culprit defense.

Editor output must be one of:

- `approved`: proceed to DB and assets,
- `revise`: Writer applies required changes and resubmits,
- `blocked`: core premise or case logic needs redesign.

### Compiler

Compiler is deterministic Python code, not LLM judgment. It owns:

- ID/reference validation,
- `case.json` writing,
- PostgreSQL `data.sql` generation,
- Neo4j `neo4j.cypher` or importable graph output,
- `asset_manifest.json` and prompt file generation,
- validation summary.

## Agent Output Discipline

Hermes/Codex role agents must return JSON only. Scripts should save prompts and final outputs under `authoring/`, for example:

- `writer_packet_N.prompt.txt`
- `writer_packet_N.json`
- `crosscheck_report_N.prompt.txt`
- `crosscheck_report_N.json`
- `editor_report_N.prompt.txt`
- `editor_report_N.json`

When Codex is used as a role runner, use the workflow's documented Codex execution path and capture the last response for JSON extraction. Do not rely on an agent self-report as validation; read generated files and run validators.

## Execution Commands

Default Hermes text-provider path:

```bash
python story-generator-workflow/scripts/run_story_workflow.py \
  --stdin \
  --case-id case_pasted_story \
  --out story-generator-workflow/out/case_pasted_story \
  --text-provider hermes
```

Codex role-runner path:

```bash
python story-generator-workflow/scripts/run_story_workflow.py \
  --stdin \
  --case-id case_pasted_story \
  --out story-generator-workflow/out/case_pasted_story \
  --text-provider codex
```

Manual prompt-only path:

```bash
python story-generator-workflow/scripts/run_story_workflow.py \
  --story /tmp/story.md \
  --case-id case_manual \
  --out story-generator-workflow/out/case_manual \
  --text-provider manual
```

## Asset Gate

Before Editor approval:

- do not generate images,
- do not freeze asset count,
- only draft visual needs.

After Editor approval:

- create `asset_manifest.json`,
- create background prompts,
- create each suspect's low/medium/high/critical portrait prompts,
- create evidence photo prompts,
- generate images through the configured provider or save prompts for batch generation,
- verify files exist and map to `visualProfiles`.

Generated visual assets should be high-quality noir/comic PNG/WebP, not placeholder SVGs.

## DB Export Requirements

Generate:

- `case.json` for BE runtime,
- `neo4j.cypher` or importable JSON for `BE/scripts/migrate_case_to_neo4j.py`,
- `data.sql` that upserts into PostgreSQL `cases(case_id, payload)`.

Validation before export:

- all IDs unique,
- all references resolve,
- contradiction required IDs exist,
- unlock IDs exist,
- all suspects have pressure style and usefulness role,
- public projection excludes forbidden keys: `secret`, `solution`, `isCulprit`, `hiddenTruth`, `privateTimeline`, `privateMotive`, `actualAction`, `secretNote`.

## Common Pitfalls

1. Generating assets before approval, causing asset/story mismatch after revisions.
2. Making the culprit the only meaningful character; the game needs cross-testimony and false leads.
3. Treating evidence as a direct answer instead of requiring comparison among evidence, testimony, and timeline.
4. Hiding necessary logic in private truth; the player must infer from public clues.
5. Adding hard validators for shallow dialogue when CaseWiki/persona/relationships should be enriched first.
6. Forgetting first-class character timelines; global timeline alone is not enough for interrogation.

## Verification Checklist

Before reporting done, verify and report real results for relevant items:

- Writer draft exists.
- Cross-check review exists.
- Editor approved before compile/assets.
- Suspect usefulness matrix passes.
- Contradiction route matrix passes.
- Culprit defense arc has four pressure states.
- Public/private leak lint passes.
- `case.json` validates.
- `data.sql` is idempotent.
- `neo4j.cypher` or import path exists.
- `asset_manifest.json` maps every required visual state.
- Generated assets, if any, are high-quality noir/comic PNG/WebP.

## Completion Report

Include:

- changed workflow files,
- generated artifact paths,
- validation commands/results,
- whether Editor gate passed,
- whether assets were generated or only prompts/manifests were produced,
- BE/FE contract deltas,
- unresolved blockers.
