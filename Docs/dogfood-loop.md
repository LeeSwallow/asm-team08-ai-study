# Dogfood QA Loop

이 프로젝트는 구현 보고만으로 완료 처리하지 않는다. 오케스트레이터가 직접 실행된 사이트를 탐방하고, 목표 UI/기능과 비교한 뒤 수정 지시를 반복한다.

## Required loop

1. Implement milestone in BE/FE/AI.
2. Run repo validation.
   - BE: `pytest -q`, `python -m compileall app tests`
   - FE: `npm run build`
   - AI: `pytest -q`, `python -m compileall app tests`
3. Start/verify the service locally or through Docker Compose.
4. Browser dogfood the app directly.
   - Navigate to the FE URL.
   - Check browser console after load and after each meaningful interaction.
   - Use visual inspection against `FE/target/chatgpt-shared-detective-interface.png`.
   - Interact with suspect selection, natural-language dialogue, evidence, contradiction, and event-driven updates.
5. Record issues with severity, repro steps, expected/actual behavior, and screenshot path when available.
6. Send precise fix requests to the responsible tmux agent.
7. Re-test after fixes.
8. Commit only stable, verified, reviewable milestones with atomic Conventional Commits.

## Visual QA criteria

The first screen must remain close to the target:

- dark noir full-screen dashboard
- left suspect cards
- central interrogation scene with character and speech bubble
- natural-language input and send action
- right evidence grid
- contradiction panel
- bottom internal system-flow strip
- no severe clipping, overflow, broken proportions, or generic admin-dashboard styling

## Functional QA criteria

The service must support the MVP loop:

- create/load case and session
- select suspect
- submit natural-language question
- receive dialogue response
- AI returns proposedEvents only
- BE validates/applies events
- FE receives/reflects session state/SSE updates
- submit contradiction
- observe objective/timeline/evidence/notebook/visual state changes where implemented

## Blockers

Treat these as blockers before accepting done:

- FE fails to build
- app cannot load in browser
- console errors on normal flow
- target UI is not recognizable
- natural-language dialogue flow broken
- FE calls AI directly
- hidden/private/solution data exposed in public payload or logs
- BE trusts AI for authoritative state changes
- generated/vendor/env files included in commits
