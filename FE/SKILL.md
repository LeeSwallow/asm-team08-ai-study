---
name: detective-agent-frontend
description: Use when implementing the Detective Agent FE investigation desk with natural-language dialogue, BE/SSE integration, accessibility, clean components, and frontend observability.
version: 1.0.0
author: Team-8
license: MIT
metadata:
  hermes:
    tags: [frontend, react, vite, sse, ux, observability, clean-code]
    related_skills: [codex]
---

# Detective Agent Frontend Skill

## Mission

Build the FE as a single-screen investigation desk that makes natural-language questioning feel central while reflecting BE session truth and SSE events.

## Visual Target

The FE must match `target/chatgpt-shared-detective-interface.png` as closely as practical. This target image is the primary UI spec for the MVP.

Required first-screen layout:

- Dark noir full-screen dashboard with near-black page background, subtle blue-gray borders, glassy panels, and red danger/accent color.
- Header: scale icon + `알리바이 교차검증형 추리 게임` on the left; `사건 파일`, `증거 목록`, `메모`, settings gear on the right.
- Left suspect column titled `용의자`: portrait cards, active card red border, status dot, suspect name/role/description, red active status text, bottom `인물 관계도` button.
- Center interrogation stage titled `심문 대상: <name> (<role>)`: cinematic background image, large character art, speech bubble, natural-language input, red send button, example prompt, and `증거 제시` button.
- Right evidence column titled `증거`: 3-column image tile grid with labels, locked evidence tile, then red-bordered `모순 사항` list.
- Bottom system-flow strip: `사용자 입력 → Character Agent → Light Rule Check → GameMaster Agent → 결과 기록` with icons and arrows.
- The above elements should be visible on initial/default load without requiring hidden navigation.

Implementation guidance:

- Use the image as a pixel/spacing/color reference, not just conceptual inspiration.
- Prefer game-like composition and cinematic panels over generic web/admin UI.
- If assets are missing, use existing `public/assets/*` images and dark overlays/placeholders while preserving the same composition.
- After changing UI, run the app/build and compare the first screen against the target; report remaining visual mismatches.

## Must Preserve

- Do not regress to forced question buttons as the primary UX.
- FE never calls AI directly.
- FE never stores or infers hidden culprit/solution truth.
- Suggested questions are hints/examples only.
- First loaded screen should visibly include selected speaker, conversation area, input, and send action.
- The first loaded screen must visually resemble `target/chatgpt-shared-detective-interface.png` before secondary pages/features are optimized.

## Development Flow

1. Read `AGENTS.md`, `Docs/implementation.md`, `../PRD.md`, and `../Docs/structure-audit.md`.
2. Inspect `target/chatgpt-shared-detective-interface.png`, `src/App.tsx`, `src/api.ts`, `src/types.ts`, `src/storage.ts`, and CSS before editing.
3. Keep API contracts typed and centralized.
4. Use reducers/adapters for SSE/session payload changes.
5. Add accessible status labels for pressure, new evidence, event connection, and errors.
6. Run `npm run build` before reporting done.
7. Visually compare the rendered first screen with the target image and list remaining differences.

## Observability Checklist

- Central logging utility exists before logs spread through components.
- Dialogue submit logs metadata only: IDs, duration, result, text length; not full free text by default.
- SSE lifecycle logs open/reconnect/error/ignored duplicate events.
- API failures surface user-visible recovery state and developer logs.
- Event reducer logs unknown event types at WARN.

## Code Smell Guardrails

- Avoid one giant `App.tsx` for new substantial logic; extract focused components/hooks.
- Avoid `any` for BE payloads.
- Avoid local-only session mutations when an API/SSE contract exists.
- Avoid hidden state that diverges from BE session truth.
- Avoid color-only signals; add text/ARIA labels.
