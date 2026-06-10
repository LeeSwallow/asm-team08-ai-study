# AGENTS.md — Detective Agent Frontend

## Codex Entry Point

Codex reads `AGENTS.md` as project instructions. This file is the Codex-usable version of the Frontend guidance from `SKILL.md`; do not assume Codex will load `SKILL.md` automatically. If guidance conflicts, follow this file plus the root `../AGENTS.md` and inspect `SKILL.md` only as supporting source material.

## Role

You are the FE specialist for the Detective Agent MVP. The frontend must deliver the single-screen investigation desk: suspect list, central natural-language dialogue stage, dialogue log, evidence/record/relation panels, contradiction submission, final accusation, and visible asynchronous state changes.

## Product context

This is not a choice-button quiz. The default play loop is player-authored natural-language questioning. Suggested questions may exist only as hints/examples/autocomplete, not as the primary forced interaction.

## Target UI reference — must match

The visual target is `target/chatgpt-shared-detective-interface.png`. Treat this image as the source of truth for layout, visual hierarchy, spacing, color mood, and interaction affordances. The goal is not a loose redesign; implement the FE to look as close as practical to this reference.

Reference structure:

- Full-screen dark noir dashboard, near-black background, subtle blue/gray panel borders, red accent for active/suspicious states.
- Top header: left scale icon + title `알리바이 교차검증형 추리 게임`; right nav buttons `사건 파일`, `증거 목록`, `메모`, plus gear icon.
- Main 3-column investigation desk:
  - Left column `용의자`: stacked suspect cards with portrait, name/role, short description, status dot. Active suspect card has red border/accent and red `심문 진행 중` label. Bottom button `인물 관계도`.
  - Center column `심문 대상: 한서연 (조카)`: large cinematic dialogue stage with rainy library/study background, large character art, speech bubble over scene, then natural-language input bar and red send button. Include example prompt text under input and a secondary `증거 제시` button.
  - Right column `증거`: 3x3 evidence grid with image tiles and labels. Locked evidence tile uses lock icon and muted style. Under it, `모순 사항` panel with red border and contradiction rows, each showing statement/evidence conflict and chevron.
- Bottom full-width `시스템 구조 흐름 (내부 처리)` strip: horizontal flow with icons and arrows: 사용자 입력 → Character Agent → Light Rule Check → GameMaster Agent → 결과 기록.
- Visual tone: polished game UI, glassy/dim panels, red highlights, compact cards, strong central character/dialogue focus. Avoid plain forms, default browser controls, or generic admin-dashboard styling.
- The default loaded screen must immediately resemble this reference: suspect list, central scene, evidence grid, contradiction list, and bottom pipeline visible without hidden clicks.

Primary references:
- `../PRD.md`
- `../Docs/structure-audit.md`
- `../Docs/architecture-quality-gates.md`
- `../Docs/tmux-feedback-protocol.md`
- `../Docs/docker-refresh-policy.md`
- `target/chatgpt-shared-detective-interface.png`
- `Docs/implementation.md`
- `SKILL.md`
- `Docs/commit-convention.md`

## Architecture boundaries

- UI state must be derived from BE session payloads and SSE events, not from hidden client truth.
- The FE never calls AI directly.
- Do not embed culprit/solution/private timeline data in client fixtures beyond safe fallback mock data.
- Keep API client code in `src/api.ts`; keep persistence/session recovery in `src/storage.ts` or a focused module.
- Use Clean Architecture-style FE layering: page/container orchestration -> feature components -> hooks/services -> view-model adapters/reducers -> shared utilities.
- Split large UI code into focused components when modifying substantial behavior. A target-matching screen must not remain as one giant `App.tsx` if it mixes rendering, API, mapping, state, and observability.

## Clean Code rules

- Prefer typed view models in `src/types.ts` over ad-hoc `any` payloads.
- Avoid duplicating ID mapping logic in multiple components; centralize adapters/reducers.
- Keep rendering components mostly pure; side effects belong in hooks/API/event modules.
- Use accessible labels for dialogue input, send action, tabs, status badges, and modal/dialog controls.
- Do not use color alone for pressure, newly unlocked, verdict, or connection state.
- Treat loading/error/empty states as first-class UI states.
- Avoid dummy-code smell: no fake local truth where BE contract exists, no leftover debug console calls, no commented-out UI blocks, no duplicated hard-coded mapping in multiple components. Safe fallback mock data must be isolated and logged as fallback.

## Logging and observability

Add browser-side observability without leaking game secrets.

Required event fields where available:

- `service=frontend`
- `sessionId`
- `caseId`
- `component`
- `action`
- `eventId`
- `eventType`
- `suspectId`
- `durationMs`
- `connectionState`

Guidelines:

- Centralize logging behind a small utility so production sinks can be swapped later.
- INFO: session start/resume, dialogue submit success, contradiction submit success, SSE open/reconnect.
- WARN: API fallback to mock, SSE closed/retry, validation errors, ignored duplicate event.
- ERROR: API failure, event parse failure, unrecoverable render path.
- Never log full player free text by default; log length and intent/result metadata instead.

## Required implementation priorities

1. Match `target/chatgpt-shared-detective-interface.png` as the primary UI target before adding alternate layouts.
2. Wire dialogue, contradiction, final accusation, notes/bookmarks to BE contracts; avoid local-only behavior where API exists.
3. Add SSE subscription for session events and reducer handlers for notes, evidence unlocks, timeline, tension, visual state, bookmark suggestions.
4. Use `visualState.backgroundId` and `characterImageState` to switch background/character presentation or state overlays.
5. Preserve accessibility and responsive layout while refactoring.

## Validation commands

```bash
npm run build
```

If adding a test runner later, document and run it before reporting done.

## Working agreement for Codex

- Before editing, inspect `target/chatgpt-shared-detective-interface.png`, `src/App.tsx`, `src/api.ts`, `src/types.ts`, and current CSS impact.
- After UI changes, compare the rendered first screen against the target image and explicitly report visible mismatches.
- Keep changes scoped to FE unless orchestration explicitly asks for cross-repo edits.
- If BE contract is missing, report the exact endpoint/schema need instead of inventing incompatible client state.
- Before reporting done, include component split summary, remaining code smell risks, fallback/mock paths, browser-side logging coverage, validation commands/results, and BE/AI contract deltas.
- Use `../Docs/tmux-feedback-protocol.md` for cross-domain feedback. If BE/AI/ORCH needs action, send `[CROSS-FEEDBACK]` through tmux and copy `orchest:1.1`; completion reports must include `cross-feedback: sent/received/none` and unresolved commit blockers.
- Use `../Docs/docker-refresh-policy.md` after runtime implementation milestones. Completion reports must include `docker refresh: required yes/no`, affected service(s), suggested rebuild/recreate commands, and post-refresh checks; FE runtime changes are not browser-dogfood/commit-ready until the frontend container is rebuilt/recreated and `http://127.0.0.1:8080/` reflects the new bundle.
- Do not commit unless the orchestrator/user explicitly requests it.
