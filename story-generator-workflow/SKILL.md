---
name: story-generator-workflow
description: Use when turning a raw mystery story into a Detective Agent case package through writer, cross-check writer, and editor approval gates before generating DB seeds and visual assets.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [detective-agent, story-generation, game-design, neo4j, postgres, assets]
    related_skills: [agentic-game-design, narrative-game-ai-contracts, writing-plans]
---

# Story Generator Workflow

## Overview

Use this workflow to convert a user-provided story into a playable Detective Agent case. Do not immediately write the final storyline, DB seed, or image prompts. First run an authoring loop: Writer drafts the game structure, Cross-check Writer attacks consistency and clue logic, and Editor approves only if the result is fun, fair, structurally valid, and asset-ready.

The Editor is the hard gate. Asset generation and DB export happen only after Editor approval.

## When to Use

Use when the user wants to:
- Provide a raw story and get a playable detective case.
- Generate suspects, timelines, evidence, contradictions, pressure personas, and culprit defense arcs.
- Produce Neo4j and PostgreSQL seed artifacts from approved story data.
- Produce backgrounds, suspect pressure-state portraits, and evidence photo assets.
- Improve game fun through cross-testimony, clue paths, and editorial feedback.

Do not use for:
- One-off prose writing without runtime case data.
- UI-only work.
- Immediate image generation before the story structure is approved.

## Required Loop

```text
source story
-> Writer draft
-> Cross-check Writer review
-> Editor gate
-> if revise/blocked: Writer revises
-> if approved: compile case package
-> validate
-> generate DB artifacts
-> generate asset manifest and assets
```

## Writer Responsibilities

Writer creates:
- public premise and opening objective
- hidden truth and solution-only fields
- suspect roster with public masks, private motives, and innocent secrets
- global truth timeline and public timeline
- first-class per-character timelines
- statements and questions
- evidence and records
- contradictions and clue paths
- culprit defense arc by pressure: low, medium, high, critical
- persona/speech style by pressure
- initial asset seeds, but not final generated images

Writer must make every suspect useful. Each suspect should either expose another suspect, be exposed by another suspect/evidence, carry a false lead, or reveal a relationship/fact that helps solve the case.

## Cross-check Writer Responsibilities

Cross-check Writer tries to break the case:
- time/location impossibilities
- missing evidence-to-statement links
- hidden-truth leakage into public text
- contradictions that cannot be solved from public clues
- suspects that do not matter
- culprit defense that collapses too early or feels arbitrary
- false leads that are unfair or disconnected

Return blocking issues and concrete fixes, not vague criticism.

## Editor Gate

The Editor judges game quality and story flow. The Editor approves only when:
- Other suspects' testimony organically helps reveal the culprit.
- Evidence puzzles require interesting comparison, not one-click answer reveal.
- The story has a clear act progression: hook, alibi collection, first contradiction, motive/opportunity pressure, final accusation.
- The culprit has a believable defense arc across pressure levels.
- Innocent suspects have secrets/false leads that are fair and useful.
- Public information is sufficient for the player to solve the case.
- Runtime structure is ready: stable IDs, unlocks, contradictions, visibility gates, asset IDs.

Score 0-3 for: cross-testimony, evidence puzzle, culprit defense, innocent suspect roles, story flow, fair difficulty, runtime structure. Require total >= 15 and at least 2 in cross-testimony, evidence puzzle, and culprit defense.

Editor output must be one of:
- approved: proceed to DB and assets
- revise: Writer applies required changes and resubmits
- blocked: core premise or case logic needs redesign

## Asset Gate

Before Editor approval:
- do not generate images
- do not freeze asset count
- only draft visual needs

After Editor approval:
- create `asset_manifest.json`
- create background prompts
- create each suspect's low/medium/high/critical portrait prompts
- create evidence photo prompts
- generate images through the configured provider or save prompts for batch generation
- verify files exist and map to visualProfiles

## DB Export

Generate:
- `case.json` for BE runtime
- `neo4j.cypher` or importable JSON for `migrate_case_to_neo4j.py`
- `data.sql` that upserts into PostgreSQL `cases(case_id, payload)`

Validation before export:
- all IDs unique
- all references resolve
- contradiction required IDs exist
- unlock IDs exist
- all suspects have pressure style and usefulness role
- public projection excludes forbidden keys: secret, solution, isCulprit, hiddenTruth, privateTimeline, privateMotive, actualAction, secretNote

## Common Pitfalls

1. Generating assets before approval. This causes mismatched portraits/evidence after revisions.
2. Making the culprit the only meaningful character. The game needs cross-testimony and false leads.
3. Treating evidence as a direct answer. Good puzzles compare evidence, testimony, and timeline.
4. Hiding necessary logic in private truth. The player must be able to infer from public clues.
5. Adding hard validators for shallow dialogue. Enrich CaseWiki/persona/relationships first unless a hard invariant is violated.
6. Forgetting first-class character timelines. Global timeline alone is not enough for interrogation.

## Verification Checklist

- [ ] Writer draft exists
- [ ] Cross-check review exists
- [ ] Editor approved
- [ ] Suspect usefulness matrix passes
- [ ] Contradiction route matrix passes
- [ ] Culprit defense arc has four pressure states
- [ ] Public/private leak lint passes
- [ ] case.json validates
- [ ] data.sql is idempotent
- [ ] neo4j.cypher/import path exists
- [ ] asset_manifest maps every required visual state
- [ ] generated assets are high-quality noir/comic PNG/WebP, not placeholders
