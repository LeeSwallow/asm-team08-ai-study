# Output Schema

이 문서는 Writer 승인 후 컴파일되는 case package의 목표 shape를 정의한다.

## 1. Case JSON Sections

```json
{
  "caseId": "case_...",
  "sceneId": "scene_...",
  "title": "...",
  "summary": "...",
  "victimId": "victim_...",
  "victimName": "...",
  "incidentTime": "...",
  "incidentLocation": "...",
  "questionLimit": 12,
  "opening": {},
  "storyline": {},
  "suspects": [],
  "characterTimelines": [],
  "evidence": [],
  "records": [],
  "relations": [],
  "statements": [],
  "questions": [],
  "contradictions": [],
  "visualProfiles": [],
  "solution": {}
}
```

필수 공개/비공개 경계:
- `solution`, `suspects[].secret`, `suspects[].isCulprit`, private timeline, private motive는 공개 API/AI prompt/SSE/FE diagnostics 금지.
- `storyline.timeline[].hidden=true`는 public projection에서 제거.
- `cluePaths[].secretNote`는 public projection에서 제거.

## 2. Character Timeline Shape

```json
{
  "characterId": "char_...",
  "publicClaims": [
    {
      "timelineId": "ctl_...",
      "time": "22:00",
      "location": "...",
      "claimedAction": "...",
      "statementId": "st_...",
      "visibilityGate": "statement_unlocked"
    }
  ],
  "perceivedEvents": [],
  "privateEvents": [
    {
      "timelineId": "ctl_private_...",
      "time": "22:02",
      "actualAction": "HIDDEN_PRIVATE_DO_NOT_EXPORT",
      "visibility": "private"
    }
  ]
}
```

## 3. Suspect Persona / Pressure Style

```json
{
  "characterId": "char_...",
  "name": "...",
  "role": "...",
  "publicProfile": "...",
  "persona": {
    "publicPersona": "...",
    "publicMask": "...",
    "privateMotive": "HIDDEN_PRIVATE_DO_NOT_EXPORT",
    "secret": "HIDDEN_PRIVATE_DO_NOT_EXPORT"
  },
  "speechStyle": {
    "register": "formal|casual|professional",
    "baseTone": "...",
    "vocabulary": [],
    "avoid": [],
    "low": { "tone": "...", "sample": "..." },
    "medium": { "tone": "...", "sample": "..." },
    "high": { "tone": "...", "sample": "..." },
    "critical": { "tone": "...", "sample": "..." }
  },
  "defenseArc": {
    "low": { "mode": "deny", "strategy": "..." },
    "medium": { "mode": "explain_away", "strategy": "..." },
    "high": { "mode": "counterattack", "strategy": "..." },
    "critical": { "mode": "collapse", "strategy": "..." }
  }
}
```

## 4. Contradiction Shape

```json
{
  "id": "con_...",
  "title": "...",
  "message": "public-facing result text",
  "reasonCode": "timeline_conflict|object_evidence|motive_chain|opportunity_gap",
  "severity": "low|medium|high|critical",
  "pressureDelta": 30,
  "suspectId": "char_...",
  "requiredStatementIds": ["st_..."],
  "requiredEvidenceIds": ["ev_..."],
  "requiredTimelineIds": ["tl_...", "ctl_..."],
  "unlocksEvidenceIds": [],
  "unlocksQuestionIds": [],
  "unlocksStatementIds": []
}
```

## 5. CaseWiki Enrichment Units

스토리가 얕아질 때 guard를 늘리기보다 다음 authoring unit을 추가한다:
- facts: knownBy/unknownBy/misledBy/liedAboutBy/confidence/sourceRefs
- evidence pages: observable details/provenance/reliability/reactionByCharacter
- relationship edges: trust/fear/debt/jealousy/conflict/disclosureEffect
- motive chains
- opportunity chains
- cover-up actions
- false leads
- innocent secrets
- witness reliability
- environmental clues
