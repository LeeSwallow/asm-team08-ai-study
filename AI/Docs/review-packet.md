# AI Review Packet - Real 3-Agent Runtime Hardening

Date: 2026-06-01

## Scope

- Hardened the dialogue path around the DOCS contract pipeline:
  `CharacterAgentInput -> DraftCharacterReply -> LightRuleCheckInput -> CheckedCharacterReply -> GameMasterAgentInput -> GameMasterProposal`.
- Treated `../Docs/story-agent-contract.md`, `../Docs/story-architecture.md`, `../Docs/service-contract-dialogue-story.md`, `../Docs/story-validation-gates.md`, and BE public payloads as the source of truth for `CharacterKnowledgePack`, persona overlays, and forbidden private refs.
- Kept AI state boundaries intact: no DB reads, no session mutation, no unlocks, no tension changes, no final verdict or final discovery decisions.

## Changed Files

- Runtime: `app/application/character_agent.py`, `app/application/light_rule_check.py`, `app/application/game_master_agent.py`, `app/graph/dialogue_graph.py`, `app/graph/common.py`
- Provider/metadata: `app/core/llm.py`, `app/api/internal_routes.py`
- Safety/schema/event policy: `app/core/guard.py`, `app/domain/proposed_events.py`, `app/schemas/agents.py`, `app/schemas/common.py`, `app/schemas/dialogue.py`
- Prompts/docs/tests: `app/prompts/*.py`, `README.md`, `Docs/implementation.md`, `tests/test_smoke.py`, `tests/test_dialogue_agents.py`

## Contract Notes

- `CharacterAgent` consumes only BE-supplied public payload data, especially `characterKnowledgePack`, `activePersonaOverlay`, `personaVariants`, `allowedStatement`, and allowed event policy refs.
- Canonical direction is bounded generative autonomy, not guard accretion. Hard invariants stay protected, while local emotional texture, relationship interpretation, memory paraphrase, scene flavor, and non-authoritative connective tissue should come from LLM generation over richer public projections.
- Agent input schemas expose canonical top-level fields, not only a payload wrapper: request/correlation IDs, message, dialogue mode, allowed statement, allowed event policy, CKP, forbidden refs, visible refs, and checked reply metadata.
- Contract-style persona variant maps are accepted and normalized. Map keys are preserved as default variant IDs when `id`/`variantId` is absent, and single `tensionLevel`/`pressureState`/`emotionalState` selectors are supported.
- Baseline vs high/critical pressure changes voice/evasiveness/hesitation wording without changing `allowedStatement` facts or source refs.
- `LightRuleCheck` validates final emitted text after repair, so `violatesCaseFacts` reflects final output.
- `GameMasterAgent` returns only public `NOTE_FACT_ADDED`, `NOTE_CONTRADICTION_CANDIDATE_ADDED`, or `BOOKMARK_SUGGESTED` proposals and rejects/filters tension, verdict, discovery, private reveal, unlock, visual, and state mutation events.
- `GameMasterAgent` suppresses all proposals when the checked reply is blocked, leaks solution terms, violates case facts, provider-degraded, or repaired for any safety/fact-scope reason.
- `ProposedEvent` now implements the canonical top-level contract fields: `type`, `payload`, `sourceRefs`, and `confidence`. All event constructors populate public source refs and confidence.
- LangGraph fallback is observable. Import/runtime fallback to the plain pipeline records `graph_runner=pipeline` and `graph_fallback_reason` in structured logs and response safety metadata.

## Bounded Autonomy Rubric

| Layer | Examples | AI implementation stance |
| --- | --- | --- |
| Hard Invariants | culprit, core method, core timeline, key evidence truth, ending criteria, private/public boundary, BE-owned session mutation | Keep guards/validators. LightRuleCheck and BE/EventProcessor should reject leaks, contradictions of fixed truth, state authority violations, final verdict/discovery, and private reveal. |
| Soft Constraints | public CharacterKnowledgePack, knownBy/unknownBy, confidence/provenance, tension/persona, relationship context, allowedEventPolicy, visible refs | Treat as guidance and retrieval substrate. If output is shallow, improve projection/retrieval/persona/prompt before adding validators. |
| Generative Freedom | dialogue phrasing, emotional texture, suspicion wording, relationship tension expression, memory paraphrase, scene flavor, plausible non-authoritative connective tissue | Allow when it does not contradict hard invariants or claim authoritative truth. Optionally surface as low-confidence NOTE/OBSERVATION/RUMOR/INTERPRETATION candidates for BE validation. |

LightRuleCheck should remain a lightweight anomaly/leakage/invariant checker, not a dialogue scripting engine. GameMasterAgent should remain an LLM-oriented contextual interpreter that proposes events from surfaced dialogue; BE validates authority, visibility, persistence, TensionPolicy, and SSE effects.

## Provider/Fallback Audit

- `AI_LLM_PROVIDER=fallback` remains an explicit deterministic degraded mode for local/test operation and exposes fallback/degraded metadata.
- Local deterministic mode is quarantined as dev/test-only and cannot satisfy production commit-ready validation. It suppresses proposed events through degraded metadata.
- `AI_LLM_PROVIDER=openai` validates API-key availability through `llm_status()`.
- If a production-shaped provider is unavailable or raises, dialogue now returns an explicit degraded service message instead of normal-looking testimony, sets `fallbackUsed/degraded/blockedReason/errorType`, and suppresses proposed events.
- If a provider succeeds but returns exactly the allowed statement, AI now reports that provider output honestly. It no longer replaces the provider response with deterministic seed text while claiming `provider=openai` and `fallbackUsed=false`.
- If a successful provider draft drifts outside statement scope but the rendered public seed is safe, AI exposes this with `runtimeDiagnostics.safety.providerDraftRepaired=true`, `providerDraftBlockedReason=case_fact_scope_repaired`, and `finalTextSource=public_seed_after_provider_scope_repair`. For explicit public contradiction context, the final emitted answer is not marked repaired/blocked, so GameMaster can still propose policy-bound `NOTE_CONTRADICTION_CANDIDATE_ADDED`. Provider drafts that include the allowed statement plus extra unapproved facts remain `repaired=true` and suppress events.
- Provider timeout metadata is exposed in health/status metadata via `timeoutMs`.
- No silent fake-success fallback is used for provider failure.
- BE can distinguish local deterministic mode from provider failure by `provider`, `fallbackUsed`, `degraded`, `blockedReason`, and `errorType`: local fallback uses `provider=deterministic-fallback`, `blockedReason=deterministic_fallback_selected`, and no `errorType`; provider failure uses `provider=openai|provider-unavailable`, provider-specific `blockedReason`, and `errorType`.

## Forbidden Ref Audit

Expanded forbidden refs are stripped from public models and guarded from output/proposals:

`secret`, `solution`, `privateTimeline`, `privateEvents`, `privateMotive`, `privateRefs`, `culprit`, `culpritId`, `isCulprit`, `finalDiscovery`, `finalVerdict`, `actualAction`, `actualLocation`, `secretNote`.

Additional private authoring extras are stripped or hidden-list-filtered defensively: `privateNote`, `culpritInference`, `isLie`, `hidden`, `hiddenSolution`, `visibility=private|hidden|secret`, and unknown keys with private/secret/hidden/culprit/solution prefixes.

## Validation

```bash
python -m compileall app tests
# passed

pytest -q
# 47 passed, 1 warning in 0.65s

pytest -q \
  tests/test_smoke.py::test_health \
  tests/test_smoke.py::test_dialogue_proposed_events_respect_policy_and_hidden_fields \
  tests/test_dialogue_agents.py::test_game_master_suppresses_events_for_fact_scope_repaired_reply \
  tests/test_dialogue_agents.py::test_game_master_suppresses_events_for_blocked_or_heavily_repaired_checked_reply \
  tests/test_dialogue_agents.py::test_agent_output_shapes_keep_cross_responsibilities_forbidden \
  tests/test_dialogue_agents.py::test_character_knowledge_pack_contract_map_preserves_variant_id_and_selectors \
  tests/test_dialogue_agents.py::test_first_class_agent_inputs_expose_contract_top_level_fields \
  tests/test_dialogue_agents.py::test_langgraph_runtime_fallback_is_observable \
  tests/test_dialogue_agents.py::test_contract_strips_private_authoring_extras_and_hidden_items \
  tests/test_smoke.py::test_dialogue_provider_unavailable_is_degraded_without_events \
  tests/test_smoke.py::test_dialogue_falls_back_when_llm_fails
# 11 passed, 1 warning in 0.31s

pytest -q \
  tests/test_dialogue_agents.py::test_guard_rejects_broad_guidance_padding_with_new_case_fact \
  tests/test_dialogue_agents.py::test_guard_repairs_clue_specific_padding_when_allowed_statement_is_unrelated \
  tests/test_dialogue_agents.py::test_guard_allows_non_factual_meta_padding_without_case_specific_context \
  tests/test_dialogue_agents.py::test_guard_preserves_clue_specific_guidance_when_public_context_terms_support_it \
  tests/test_smoke.py::test_dialogue_runtime_diagnostics_include_safe_ai_metadata
# 5 passed, 1 warning in 0.30s

pytest -q \
  tests/test_smoke.py::test_dialogue_be_proxy_study_entry_context_keeps_ai_contradiction_event \
  tests/test_smoke.py::test_dialogue_provider_drift_to_public_seed_still_allows_policy_bound_contradiction \
  tests/test_smoke.py::test_dialogue_guard_rejects_new_case_facts \
  tests/test_dialogue_agents.py::test_game_master_suppresses_events_for_fact_scope_repaired_reply
# 4 passed, 1 warning in 0.31s
```

Warning observed: Starlette/FastAPI TestClient deprecation warning for `httpx`; not caused by this runtime change.

## Docker Refresh

- Required: yes
- Services: `ai`, then recreate `backend` for integration behavior that depends on AI responses
- Reason: AI runtime/schema/provider behavior changed
- Suggested commands:

```bash
cd /home/min/Projects/Swmaestro/02-AI-SKILL-STUDY/Detective_Agent
docker compose build ai
docker compose up -d --no-deps ai
docker compose up -d --no-deps backend
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:8000/api/v1/health
```

## Remaining Risks / Blockers

- Commit-ready remains blocked until independent code review passes.
- Commit-ready remains blocked until BE-mediated smoke proves the real AI path is used, not canned/mock/local fallback.
- Integration should verify BE treats degraded provider responses as non-progress and does not apply proposed events when AI returns fallback/degraded metadata.
- Integration should verify BE/FE preserve and display AI-owned public diagnostics: `intent`, `provider`, `model`, `safety`, `matchedRefs`, `runtimeDiagnostics`, and `proposedEventsCount`. BE remains owner of applied event counts.
- `_padding_is_safe` is now context-aware for clue/evidence/medical/location/action terms. Globally safe padding no longer preserves clue-specific text such as lipstick/medical guidance unless the allowed statement or public BE payload context terms support it.
- Deferred risk: `_padding_is_safe` still uses a conservative phrase allowlist for non-factual padding. This is intentionally conservative for MVP safety, but new persona phrases should add tests or move to a stronger factual-claim classifier.
- Architecture warning: the current safe-padding allowlist and dogfood phrase tuning are MVP scaffolding, not the desired long-term content engine. Next quality work should replace one-off phrasing patches with richer CaseWiki/CharacterKnowledgePack projection, deterministic public retrieval, and prompt contracts that preserve LLM autonomy under light verification.
- To reduce guard accretion, `_padding_is_safe` now also accepts compact non-factual meta-investigative guidance based on bounded patterns instead of requiring every safe phrase to be mirrored exactly in the allowlist. It rejects secret/private terms, unsupported clue-specific context, and case-entity factual declarations such as medication/location/action claims outside `allowedStatement` plus public current-turn context.
- Hidden/private object policy: list fields drop hidden/private entries before model validation. A hidden/private object supplied as an entire root object still sanitizes to an empty object and may fail validation if required public fields are absent; this is acceptable because BE should not send hidden root payloads, and list-mixed hidden public projections are covered by tests.

## Next AI Quality Milestone

Character-specific public timeline retrieval and GameMaster event-link context should be handled as a follow-up quality milestone after this runtime hardening commit is independently reviewed and BE-smoked. This fits the AI scope, but it is intentionally deferred to avoid mixing broad prompt/retrieval/event-ranking rewrites into the current commit blocker fix.

Proposed files:

- Add `app/domain/context_retriever.py`
- Update `app/application/character_agent.py` to use `DialogueRenderContext` in `_knowledge_prompt_context`
- Update `app/application/game_master_agent.py` and `app/domain/proposed_events.py` to use `EventLinkContext` for event proposal inputs
- Update `app/prompts/dialogue.py` with structured sections: `ROLE_SKILL`, `CURRENT_ALLOWED_FACT`, `RETRIEVED_PUBLIC_MEMORY`, `RESPONSE_POLICY`, `EVENT_POLICY_HINT`
- Add tests in `tests/test_context_retriever.py` or extend `tests/test_dialogue_agents.py`

Proposed behavior:

- Deterministically rank only BE-provided public `CharacterKnowledgePack` and `characterTimeline` data.
- Expose two projections from the same public-only retriever:
  - `DialogueRenderContext` for CharacterAgent prompt/voice shaping.
  - `EventLinkContext` for GameMasterAgent note/bookmark/contradiction proposal inputs.
- `DialogueRenderContext` returns sections such as `persona_skill`, `active_alibi`, `evidence_links`, `relationship_pressure`, `recent_memory`, and `guardrails`.
- `EventLinkContext` includes `checkedReply.sourceRefs`/`usedRefs`, `allowedStatement.sourceRefs`, `allowedEventPolicy.related*` refs, selected current-suspect timeline entries, visible evidence/statement/relationship snippets, public recent dialogue refs, and candidate graph edges such as `statement -> timeline -> evidence -> contradiction -> relationship`.
- Select 3-6 snippets by intent, current question, `allowedEventPolicy` refs, tension/emotion, and recent dialogue.
- Keep `allowedStatement` as the only new factual claim allowed; retrieved snippets shape voice, chronology, pressure continuity, and event-policy context only.
- Keep BE as final validator/EventProcessor authority. GameMaster may still only propose `NOTE_FACT_ADDED`, `NOTE_CONTRADICTION_CANDIDATE_ADDED`, and `BOOKMARK_SUGGESTED`; never tension, visual, unlock, final verdict/discovery, private reveal, or mutation events.
- Event ranking priority: `allowedEventPolicy` refs first, checked reply source refs second, current suspect/intent timeline and evidence links third. Relationship snippets can influence note/bookmark suggestions only when visible and allowed this turn or directly linked to allowed evidence/statement. Unrelated visible refs must not create progress.

Proposed tests:

- Timeline ordering: a time/location question selects the current suspect's matching `characterTimeline.events` before unrelated global timeline items.
- Intent-aware retrieval: timeline questions prefer alibi/timeline snippets; evidence questions prefer evidence-linked context; pressure follow-ups prefer recent dialogue plus persona overlay.
- Public/private guard: forbidden tokens and hidden/private refs are dropped before prompt construction.
- Prompt regression: selected timeline source IDs appear in the prompt, and unrelated visible refs are excluded when `allowedEventPolicy` narrows scope.
- Provider degraded unchanged: retrieval only shapes prompt; provider-degraded responses and GameMaster event suppression remain unchanged.
- GameMaster source refs come from `EventLinkContext` and allowed refs, not arbitrary visible refs.
- Evidence plus relationship links produce notes/bookmarks only when allowed by this turn's policy or directly linked to allowed evidence/statement.
- Relationship context never bypasses `allowedEventPolicy`.
- Repaired, blocked, leaky, or degraded checked replies still produce empty `proposedEvents` even if `EventLinkContext` has candidates.
- Unrelated visible evidence/relationship snippets cannot produce note, contradiction, or bookmark progress.

Contract note: BE should continue sending `characterTimeline.events` and `CharacterKnowledgePack` visible timeline/alibi/evidence/relationship snippets as public projections. Later wiki/skill authoring can compile into stable IDs, with BE filtering visibility before AI receives it.

## Recommended Commit Split

1. `feat(ai): add first-class dialogue agent contracts`
   - `app/schemas/agents.py`, agent orchestration, graph node contract wiring.
2. `feat(ai): harden story-grounded character generation`
   - CharacterKnowledgePack/persona overlay normalization, tension voice behavior, prompt updates.
3. `fix(ai): surface provider degradation without fake testimony`
   - provider/env health metadata, degraded response behavior, no event proposals on provider failure.
4. `fix(ai): enforce public-only game master proposals`
   - forbidden event filtering, checked-reply safety gating, private payload stripping.
5. `test(ai): cover story contract safety gates`
   - persona overlay, provider degraded, forbidden refs/extras, health, GM suppression tests.
