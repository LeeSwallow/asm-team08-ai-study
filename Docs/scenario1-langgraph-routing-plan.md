# Scenario1 LangGraph Character Reaction Routing Plan

## 목표

feedback2.md를 주 기준으로 scenario1의 자연어 심문 구조를 고도화한다. 핵심은 대화 상대 라우팅이 아니라 현재 선택된 CharacterAgent가 플레이어 발화를 판단하고 reaction route를 소유하는 구조다. LangGraph `add_conditional_edges` 또는 동일 수준의 route-aware fallback을 반드시 사용한다.

feedback.md는 부분 반영한다. `respond_only/propose_branch`의 철학 중 “LLM은 안전한 제안 branch만 소유하고 BE는 권위 있는 state mutation을 검증한다”는 원칙을 CharacterReactionDecision의 `stateIntent`/diagnostics에 흡수한다.

## 구현 단위 및 커밋 계획

### Commit 1 — docs/feedback 기준선과 계획
- 포함 파일: `feedback.md`, `feedback2.md`, `Docs/scenario1-langgraph-routing-plan.md`
- 검증: 문서 파일 존재 및 요구사항 추적 가능

### Commit 2 — CharacterReaction schema/agent/validator + RED/GREEN tests
- 추가/수정:
  - `BE/app/ai_engine/schemas/agents.py`
  - `BE/app/ai_engine/agents/character_reaction_judge_agent.py`
  - `BE/tests/test_character_reaction_judge.py`
- 기능:
  - 7개 route enum: `answer_relevant`, `deflect_irrelevant`, `reject_false_premise`, `challenge_player_contradiction`, `react_to_valid_pressure`, `ask_clarification`, `refuse_meta_or_private`
  - 공개 refs만 유지하는 validator
  - `stateIntent`는 제안만 허용, 직접 적용 금지
- 테스트:
  - 정상 질문, 뜬금없는 질문, 근거 없는 단정, 공개정보 모순, 유효 압박, 모호한 질문, 메타/비공개 유도

### Commit 3 — LangGraph conditional edge 및 route nodes
- 추가/수정:
  - `BE/app/ai_engine/graph/dialogue_graph.py`
  - `BE/app/ai_engine/graph/dialogue_generation_nodes.py`
  - `BE/app/ai_engine/graph/dialogue_nodes.py`
  - `BE/app/ai_engine/graph/dialogue_response_nodes.py`
  - `BE/app/ai_engine/agents/character_agent.py`
  - `BE/app/ai_engine/agents/character_seed.py`
  - `BE/tests/test_dialogue_reaction_conditional_edges.py`
- 기능:
  - `CharacterReactionJudgeAgent -> CharacterReactionValidator -> add_conditional_edges(route)`
  - route별 `DialogueDirectorPlan` 생성
  - route-aware fallback runner
  - runtimeDiagnostics에 `characterReaction`, `characterReactionRoute`, `conditionalRouteOwner` 포함
- 테스트:
  - route가 실제 route node/functionCall로 이어지는지 확인
  - LangGraph unavailable fallback도 동일 route를 탄다는 것 확인

### Commit 4 — review/librarian 자기검증 루프
- 추가/수정:
  - `BE/app/ai_engine/agents/reaction_review_agent.py`
  - `BE/app/ai_engine/agents/reaction_librarian_agent.py`
  - `BE/app/ai_engine/graph/dialogue_generation_nodes.py`
  - `BE/tests/test_reaction_review_librarian.py`
- 기능:
  - ReviewAgent: route/plan의 안전성, 공개 refs, route-plan 일관성 자체검증
  - LibrarianAgent: route decision과 route plan을 안전한 public route card로 정리하여 diagnostics/FE가 읽을 수 있게 보존
  - review 실패 시 safe route로 강등
- 테스트:
  - private/unknown refs 및 high-impact route without evidence가 review로 강등됨
  - librarian card가 public-only이며 player-facing label/reason을 제공

### Commit 5 — FE/BE public contract + docs/scenario update
- 추가/수정:
  - `BE/app/application/dialogue_service.py` 또는 local AI adapter 공개 필터
  - `FE/src/types.ts`
  - `FE/src/adapters/sessionAdapter.ts`
  - `FE/src/components/InterrogationStage.tsx`
  - `FE/src/hooks/useInvestigationSession.ts`
  - `Docs/agentic-interrogation-flow.md`
  - `Docs/Senario/case-001.md` 또는 별도 note
- 기능:
  - FE에 “AI 판단 route” badge/diagnostic 표시
  - scenario1 authoring docs에 route별 플레이 경험 및 안전 경계 명시
- 테스트:
  - BE pytest
  - FE `npm run build`

### Commit 6 — 최종 검증/정리
- 검증:
  - `cd BE && pytest -q`
  - `cd BE && python -m compileall app tests`
  - `cd FE && npm run build`
  - 필요 시 Docker Compose 서비스 rebuild/recreate와 health check
- 외부 review:
  - Claude Code 또는 Codex CLI로 diff review 수행
  - blocking/high-signal findings 수정 후 재검증

## Acceptance Criteria

1. LangGraph graph code에 실제 `add_conditional_edges`가 존재한다.
2. route map에 feedback2의 7개 reaction route가 모두 등록된다.
3. CharacterReactionJudgeAgent가 플레이어 발화의 관련성/근거성/모순성/압박성/메타성을 판단한다.
4. CharacterAgent는 route별 plan을 받아 답변 전략을 바꾼다.
5. LightRuleCheck와 GameMasterAgent는 downstream으로 유지된다.
6. BE는 hidden/private refs와 권위 있는 state mutation을 계속 검증한다.
7. ReviewAgent와 LibrarianAgent가 자기검증/피드백 루프를 수행한다.
8. FE/diagnostics에서 route, confidence, public reason이 확인된다.
9. feedback.md의 branch-owner 원칙은 safe proposal/stateIntent boundary로 반영된다.
