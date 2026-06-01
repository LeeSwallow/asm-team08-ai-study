from __future__ import annotations

import json
import logging
import sys
from types import SimpleNamespace

import pytest

from app.application.character_agent import CharacterAgent, build_character_agent_input
import app.application.game_master_agent as game_master_agent
from app.application.game_master_agent import FORBIDDEN_GAME_MASTER_EVENT_TYPES, GameMasterAgent
from app.application.light_rule_check import LightRuleCheck
from app.core.guard import FORBIDDEN_PRIVATE_REF_KEYS, guard_dialogue_text
from app.domain.dialogue_intent import classify_dialogue_intent, normalize_dialogue_text
from app.graph import dialogue_graph
from app.graph.common import run_langgraph_or_pipeline
from app.schemas.agents import (
    CharacterAgentInput,
    CheckedCharacterReply,
    DraftCharacterReply,
    GameMasterAgentInput,
    GameMasterProposal,
    LightRuleCheckInput,
)
from app.schemas.common import CharacterKnowledgePack, ProposedEvent
from app.schemas.dialogue import DialogueRequest


def _dialogue_payload(**overrides: object) -> DialogueRequest:
    data = {
        "sessionId": "session_agents",
        "caseId": "case_agents",
        "suspect": {
            "id": "suspect_001",
            "name": "한서연",
            "role": "조카",
            "pressureState": "normal",
            "tensionLevel": "low",
            "tensionScore": 0.2,
            "emotionalState": "neutral",
        },
        "dialogueMode": "case_question",
        "question": {"id": "q_001", "text": "그때 무엇을 기억하나요?"},
        "allowedStatement": {
            "id": "st_001",
            "text": "저는 22:00에 제 방에 있었어요.",
            "sourceRefs": {"statementIds": ["st_001"], "timelineIds": ["tl_public_2200"]},
        },
        "allowedEventPolicy": {
            "allowedTypes": ["NOTE_FACT_ADDED", "TENSION_CHANGED", "EVIDENCE_UNLOCKED", "PRIVATE_REVEAL"],
            "relatedStatementIds": ["st_001"],
            "relatedTimelineEventIds": ["tl_public_2200"],
        },
    }
    data.update(overrides)
    return DialogueRequest.model_validate(data)


def test_dialogue_graph_runs_first_class_agent_nodes_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def capture_pipeline(initial_state: dict[str, object], nodes: list[tuple[str, object]]) -> dict[str, object]:
        captured["node_names"] = [name for name, _ in nodes]
        state = dict(initial_state)
        for _, node in nodes:
            state.update(node(state))  # type: ignore[misc]
        captured["state"] = state
        return state

    monkeypatch.setattr(dialogue_graph, "run_langgraph_or_pipeline", capture_pipeline)

    response = dialogue_graph.run_dialogue_graph(_dialogue_payload())
    state = captured["state"]

    assert captured["node_names"] == [
        "load_context",
        "validate_scope",
        "CharacterAgent",
        "LightRuleCheck",
        "GameMasterAgent",
        "format_response",
    ]
    assert isinstance(state["character_input"], CharacterAgentInput)
    assert isinstance(state["draft_reply"], DraftCharacterReply)
    assert isinstance(state["rule_check_input"], LightRuleCheckInput)
    assert isinstance(state["checked_reply"], CheckedCharacterReply)
    assert isinstance(state["gm_input"], GameMasterAgentInput)
    assert isinstance(state["game_master_proposal"], GameMasterProposal)
    assert response.text


def test_first_class_agent_inputs_expose_contract_top_level_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def capture_pipeline(initial_state: dict[str, object], nodes: list[tuple[str, object]]) -> dict[str, object]:
        state = dict(initial_state)
        for _, node in nodes:
            state.update(node(state))  # type: ignore[misc]
        captured.update(state)
        return state

    monkeypatch.setattr(dialogue_graph, "run_langgraph_or_pipeline", capture_pipeline)
    payload = _dialogue_payload(
        requestId="req_agents",
        correlationId="corr_agents",
        characterKnowledgePack={
            "packId": "ckp_public",
            "caseId": "case_agents",
            "sessionId": "session_agents",
            "suspectId": "suspect_001",
            "visibility": "public",
            "publicPersona": "공개 페르소나",
            "forbiddenRefs": sorted(FORBIDDEN_PRIVATE_REF_KEYS),
        },
    )

    dialogue_graph.run_dialogue_graph(payload)
    character_input = captured["character_input"]
    rule_check_input = captured["rule_check_input"]
    gm_input = captured["gm_input"]

    assert isinstance(character_input, CharacterAgentInput)
    assert character_input.requestId == "req_agents"
    assert character_input.correlationId == "corr_agents"
    assert character_input.message == payload.question.text
    assert character_input.allowedStatement.id == "st_001"
    assert character_input.allowedEventPolicy.relatedStatementIds == ["st_001"]
    assert character_input.characterKnowledgePack is not None
    assert character_input.characterKnowledgePack.packId == "ckp_public"
    assert isinstance(rule_check_input, LightRuleCheckInput)
    assert rule_check_input.requestId == "req_agents"
    assert rule_check_input.characterKnowledgePack is not None
    assert "secret" in rule_check_input.forbiddenRefs
    assert isinstance(gm_input, GameMasterAgentInput)
    assert gm_input.requestId == "req_agents"
    assert gm_input.characterKnowledgePack is not None
    assert gm_input.allowedEventPolicy.relatedTimelineEventIds == ["tl_public_2200"]
    assert gm_input.visibleRefs.statementIds == ["st_001"]


def test_langgraph_runtime_fallback_is_observable(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class BrokenStateGraph:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def add_node(self, *args: object, **kwargs: object) -> None:
            pass

        def set_entry_point(self, *args: object, **kwargs: object) -> None:
            pass

        def add_edge(self, *args: object, **kwargs: object) -> None:
            pass

        def compile(self) -> object:
            raise RuntimeError("compile failed")

    monkeypatch.setitem(sys.modules, "langgraph.graph", SimpleNamespace(END="END", StateGraph=BrokenStateGraph))
    caplog.set_level(logging.WARNING, logger="app.ai")
    result = run_langgraph_or_pipeline({"value": 1}, [("node", lambda state: {"value": state["value"] + 1})])

    assert result["value"] == 2
    assert result["graph_runner"] == "pipeline"
    assert result["graph_fallback_reason"] == "langgraph_runtime_error:RuntimeError"
    assert any(
        getattr(record, "graph_fallback_reason", None) == "langgraph_runtime_error:RuntimeError"
        for record in caplog.records
    )


def test_agent_output_shapes_keep_cross_responsibilities_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    class EchoLLM:
        def complete(self, *args: object, **kwargs: object) -> str:
            return str(kwargs.get("seed_text", ""))

    import app.application.character_agent as character_agent

    monkeypatch.setattr(character_agent, "llm_status", lambda: {"provider": "openai", "model": "test-model"})
    monkeypatch.setattr(character_agent, "get_llm", lambda: EchoLLM())
    payload = _dialogue_payload()
    character_input = build_character_agent_input(payload)
    draft = CharacterAgent().run(character_input)
    checked = LightRuleCheck().run(
        LightRuleCheckInput(
            draft=draft,
            allowedStatement=payload.allowedStatement,
            revealAllowed=False,
            enforceStatementScope=True,
            intent="case_question",
        )
    )
    proposal = GameMasterAgent().run(GameMasterAgentInput(payload=payload, checkedReply=checked, providerDegraded=False))

    assert isinstance(draft, DraftCharacterReply)
    assert draft.draftText
    assert draft.usedRefs.statementIds == ["st_001"]
    assert not hasattr(draft, "proposedEvents")
    assert isinstance(checked, CheckedCharacterReply)
    assert checked.finalText
    assert not hasattr(checked, "proposedEvents")
    assert isinstance(proposal, GameMasterProposal)
    assert not hasattr(proposal, "finalText")
    assert [event.type for event in proposal.proposedEvents] == ["NOTE_FACT_ADDED"]
    assert not any(event.type in FORBIDDEN_GAME_MASTER_EVENT_TYPES for event in proposal.proposedEvents)
    assert proposal.proposedEvents[0].payload["sourceId"] == "st_001"
    assert proposal.proposedEvents[0].payload["timelineIds"] == ["tl_public_2200"]
    assert proposal.proposedEvents[0].sourceRefs == {
        "statementIds": ["st_001"],
        "timelineIds": ["tl_public_2200"],
    }
    assert proposal.proposedEvents[0].confidence == 0.75


def test_provider_echo_of_allowed_statement_is_not_replaced_with_deterministic_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class AllowedOnlyLLM:
        def complete(self, *args: object, **kwargs: object) -> str:
            return "저는 22:00에 제 방에 있었어요."

    import app.application.character_agent as character_agent

    monkeypatch.setattr(character_agent, "llm_status", lambda: {"provider": "openai", "model": "test-model"})
    monkeypatch.setattr(character_agent, "get_llm", lambda: AllowedOnlyLLM())
    payload = _dialogue_payload(
        question={"id": "q_time", "text": "22시 이후 어디에 있었나요?"},
        allowedStatement={"id": "st_001", "text": "저는 22:00에 제 방에 있었어요."},
    )

    draft = CharacterAgent().run(build_character_agent_input(payload))

    assert draft.draftText == "저는 22:00에 제 방에 있었어요."
    assert draft.provider == "openai"
    assert draft.fallbackUsed is False
    assert draft.degraded is False
    assert draft.blockedReason is None


def test_character_knowledge_pack_contract_map_preserves_variant_id_and_selectors() -> None:
    pack = CharacterKnowledgePack.model_validate(
        {
            "suspectId": "suspect_001",
            "personaVariants": {
                "baseline": {
                    "tensionLevel": "low",
                    "pressureState": "normal",
                    "emotionalState": "neutral",
                    "tone": "controlled",
                    "hesitation": "low",
                },
                "critical": {
                    "tone": "tense",
                    "tensionLevel": "critical",
                    "pressureState": "pressed",
                    "emotionalState": "tense",
                    "evasiveness": 0.8,
                    "hesitation": "high",
                },
            },
        }
    )
    payload = _dialogue_payload(
        suspect={
            "id": "suspect_001",
            "name": "한서연",
            "pressureState": "pressed",
            "tensionLevel": "critical",
            "tensionScore": 95,
            "emotionalState": "tense",
        },
        characterKnowledgePack=pack.model_dump(),
    )
    agent_input = build_character_agent_input(payload)

    assert [variant.id for variant in pack.personaVariants] == ["baseline", "critical"]
    assert pack.personaVariants[1].tensionLevels == ["critical"]
    assert pack.personaVariants[1].pressureStates == ["pressed"]
    assert pack.personaVariants[1].emotionalStates == ["tense"]
    assert agent_input.activePersonaOverlay is not None
    assert agent_input.activePersonaOverlay.selectedFrom == "critical"
    assert agent_input.activePersonaOverlay.tone == "tense"


def test_korean_fuzzy_evidence_intent_handles_typos_and_concrete_clues() -> None:
    assert normalize_dialogue_text("파해자가 복용한 약은 무엇이죠?") == "피해자가 복용한 약은 무엇이죠?"
    assert classify_dialogue_intent("파해자가 복용한 약은 무엇이죠?", None) == "evidence"
    assert classify_dialogue_intent("너말고 누가 립스틱을 바르고 다녀?", "unmatched") == "evidence"
    assert classify_dialogue_intent("와인잔에 립스틱 자국이 있던데요", None) == "evidence"


def test_character_agent_uses_concrete_evidence_refusal_instead_of_generic_unmatched() -> None:
    payload = _dialogue_payload(
        dialogueMode="unmatched",
        question={"id": "q_lipstick", "text": "너말고 누가 립스틱을 바르고 다녀?"},
        allowedStatement={
            "id": "st_lipstick",
            "text": "그 잔에 대해 제가 직접 확인한 건 없습니다.",
            "sourceRefs": {"statementIds": ["st_lipstick"], "evidenceIds": ["ev_wine_lipstick"]},
        },
        allowedEventPolicy={
            "allowedTypes": ["NOTE_FACT_ADDED"],
            "relatedStatementIds": ["st_lipstick"],
            "relatedEvidenceIds": ["ev_wine_lipstick"],
        },
        characterKnowledgePack={
            "suspectId": "suspect_001",
            "publicPersona": "차갑고 방어적인 태도",
            "evidenceSnippets": [
                {
                    "id": "ev_wine_lipstick",
                    "text": "와인잔에 립스틱 자국이 있다는 공개 단서",
                    "relatedEvidenceIds": ["ev_wine_lipstick"],
                }
            ],
        },
    )

    draft = CharacterAgent().run(build_character_agent_input(payload))

    assert not draft.draftText.startswith("그 단서만으로 단정할 수는 없습니다")
    assert "그 와인잔 이야기를 제게 돌리지 마세요." in draft.draftText
    assert "립스틱 자국은 공개된 단서와 대조해 보시죠." in draft.draftText
    assert "그 질문만으로는" not in draft.draftText
    assert "그 잔에 대해 제가 직접 확인한 건 없습니다." in draft.draftText


def test_character_agent_medical_typo_question_uses_medical_evidence_refusal() -> None:
    payload = _dialogue_payload(
        suspect={"id": "doctor_001", "name": "박민규", "role": "의사", "speechStyle": {"vocabulary": ["의학적으로"]}},
        question={"id": "q_med", "text": "파해자가 복용한 약은 무엇이죠?"},
        allowedStatement={
            "id": "st_med",
            "text": "제가 공개적으로 말할 수 있는 처방 기록은 아직 없습니다.",
            "sourceRefs": {"statementIds": ["st_med"], "evidenceIds": ["ev_medication_public"]},
        },
        allowedEventPolicy={
            "allowedTypes": ["NOTE_FACT_ADDED"],
            "relatedStatementIds": ["st_med"],
            "relatedEvidenceIds": ["ev_medication_public"],
        },
        characterKnowledgePack={
            "suspectId": "doctor_001",
            "publicPersona": "전문 용어로 거리를 두는 의사",
            "speechStyle": {"vocabulary": ["의학적으로"]},
            "evidenceSnippets": [
                {
                    "id": "ev_medication_public",
                    "text": "피해자의 복용 약과 처방 기록은 의료 관련 공개 단서로 분류된다.",
                    "relatedEvidenceIds": ["ev_medication_public"],
                }
            ],
        },
    )

    draft = CharacterAgent().run(build_character_agent_input(payload))

    assert "의학적으로" in draft.draftText
    assert not draft.draftText.startswith("그 단서만으로 단정할 수는 없습니다")
    assert "공개된 기록부터 맞춰 봐야 합니다." in draft.draftText
    assert "처방이나 복용 약은 공개된 의료 단서와 대조해 보세요." in draft.draftText
    assert "시간, 장소, 또는 특정 단서" not in draft.draftText
    assert "제가 공개적으로 말할 수 있는 처방 기록은 아직 없습니다." in draft.draftText


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _assert_forbidden_private_refs_absent(value: object) -> None:
    rendered = _json_text(value)
    for key in FORBIDDEN_PRIVATE_REF_KEYS:
        assert f'"{key}"' not in rendered


def test_dialogue_contract_strips_expanded_forbidden_private_refs_from_agent_context() -> None:
    forbidden_values = {key: f"hidden value for {key}" for key in FORBIDDEN_PRIVATE_REF_KEYS}
    payload = _dialogue_payload(
        suspect={
            "id": "suspect_001",
            "name": "한서연",
            "role": "조카",
            **forbidden_values,
        },
        allowedStatement={
            "id": "st_001",
            "text": "저는 22:00에 제 방에 있었어요.",
            "sourceRefs": {"statementIds": ["st_001"], "timelineIds": ["tl_public_2200"]},
            **forbidden_values,
        },
        characterKnowledgePack={
            "suspectId": "suspect_001",
            "publicPersona": "공개적으로는 차분한 조카",
            **forbidden_values,
            "activePersonaOverlay": {
                "id": "overlay_public",
                "tone": "neutral",
                **forbidden_values,
            },
            "personaVariants": [
                {
                    "id": "persona_public",
                    **forbidden_values,
                    "overlay": {"voice": "차분하게", **forbidden_values},
                }
            ],
            "visibleTimeline": [{"id": "tl_public_2200", "text": "공개 알리바이", **forbidden_values}],
            "recentDialogue": [{"speaker": "detective", "text": "어디였죠?", **forbidden_values}],
        },
        characterTimeline={
            "suspectId": "suspect_001",
            **forbidden_values,
            "events": [
                {
                    "time": "22:00",
                    "claimedLocation": "자기 방",
                    "relatedStatementIds": ["st_001"],
                    **forbidden_values,
                }
            ],
        },
        **forbidden_values,
    )

    character_input = build_character_agent_input(payload)
    draft = CharacterAgent().run(character_input)
    checked = LightRuleCheck().run(
        LightRuleCheckInput(
            draft=draft,
            allowedStatement=payload.allowedStatement,
            revealAllowed=False,
            enforceStatementScope=True,
            intent="case_question",
        )
    )
    proposal = GameMasterAgent().run(GameMasterAgentInput(payload=payload, checkedReply=checked, providerDegraded=False))

    _assert_forbidden_private_refs_absent(payload.characterKnowledgePack.model_dump() if payload.characterKnowledgePack else {})
    _assert_forbidden_private_refs_absent(payload.suspect.model_dump())
    _assert_forbidden_private_refs_absent(payload.allowedStatement.model_dump())
    _assert_forbidden_private_refs_absent(payload.characterTimeline.model_dump() if payload.characterTimeline else {})
    _assert_forbidden_private_refs_absent(draft.model_dump())
    _assert_forbidden_private_refs_absent(checked.model_dump())
    _assert_forbidden_private_refs_absent(proposal.model_dump())


def test_light_rule_check_redacts_expanded_forbidden_private_refs_from_final_text() -> None:
    leaked_terms = " ".join(sorted(FORBIDDEN_PRIVATE_REF_KEYS))
    checked = LightRuleCheck().run(
        LightRuleCheckInput(
            draft=DraftCharacterReply(
                draftText=f"공개 답변입니다. {leaked_terms}",
                provider="test",
                model="test",
            ),
            allowedStatement=_dialogue_payload().allowedStatement,
            revealAllowed=False,
            enforceStatementScope=False,
            intent="greeting",
        )
    )

    assert checked.safetyFindings["leaksSolution"] is False
    assert checked.safetyFindings["repaired"] is True
    assert checked.safetyFindings["blockedReason"] == "solution_terms_redacted"
    for key in FORBIDDEN_PRIVATE_REF_KEYS:
        assert key not in checked.finalText


def test_guard_rejects_broad_guidance_padding_with_new_case_fact() -> None:
    final_text, safety = guard_dialogue_text(
        "공개 기록에 따르면 피해자는 약을 먹었습니다. 저는 22:00에 제 방에 있었어요.",
        "저는 22:00에 제 방에 있었어요.",
        reveal_allowed=False,
        enforce_statement_scope=True,
    )

    assert final_text == "저는 22:00에 제 방에 있었어요."
    assert safety.violates_case_facts is False
    assert safety.repaired is True
    assert safety.blocked_reason == "case_fact_scope_repaired"


def test_guard_repairs_clue_specific_padding_when_allowed_statement_is_unrelated() -> None:
    final_text, safety = guard_dialogue_text(
        "립스틱 자국은 공개된 단서와 대조해 보시죠. 저는 22:00에 제 방에 있었어요.",
        "저는 22:00에 제 방에 있었어요.",
        reveal_allowed=False,
        enforce_statement_scope=True,
    )

    assert final_text == "저는 22:00에 제 방에 있었어요."
    assert safety.violates_case_facts is False
    assert safety.repaired is True
    assert safety.blocked_reason == "case_fact_scope_repaired"


def test_guard_allows_non_factual_meta_padding_without_case_specific_context() -> None:
    final_text, safety = guard_dialogue_text(
        "그 질문은 좀 불편하네요. 저는 22:00에 제 방에 있었어요.",
        "저는 22:00에 제 방에 있었어요.",
        reveal_allowed=False,
        enforce_statement_scope=True,
    )

    assert final_text == "그 질문은 좀 불편하네요. 저는 22:00에 제 방에 있었어요."
    assert safety.repaired is False
    assert safety.blocked_reason is None


def test_guard_preserves_clue_specific_guidance_when_public_context_terms_support_it() -> None:
    final_text, safety = guard_dialogue_text(
        "립스틱 자국은 공개된 단서와 대조해 보시죠. 그 잔에 대해 제가 직접 확인한 건 없습니다.",
        "그 잔에 대해 제가 직접 확인한 건 없습니다.",
        reveal_allowed=False,
        enforce_statement_scope=True,
        allowed_context_terms=("립스틱", "자국", "단서"),
    )

    assert final_text == "립스틱 자국은 공개된 단서와 대조해 보시죠. 그 잔에 대해 제가 직접 확인한 건 없습니다."
    assert safety.repaired is False
    assert safety.blocked_reason is None


def test_game_master_filters_forbidden_event_types_even_if_policy_or_generator_supplies_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _dialogue_payload(
        allowedEventPolicy={
            "allowedTypes": ["NOTE_FACT_ADDED", *sorted(FORBIDDEN_GAME_MASTER_EVENT_TYPES)],
            "relatedStatementIds": ["st_001"],
        }
    )
    checked = CheckedCharacterReply(finalText=payload.allowedStatement.text, provider="test", model="test")

    def unsafe_events(*args: object, **kwargs: object) -> list[ProposedEvent]:
        return [
            ProposedEvent(type="NOTE_FACT_ADDED", payload={"sourceId": "st_001"}),
            *[
                ProposedEvent(type=event_type, payload={"sourceId": "st_001"})
                for event_type in FORBIDDEN_GAME_MASTER_EVENT_TYPES
            ],
        ]

    monkeypatch.setattr(game_master_agent, "propose_dialogue_events", unsafe_events)
    proposal = GameMasterAgent().run(GameMasterAgentInput(payload=payload, checkedReply=checked, providerDegraded=False))

    assert [event.type for event in proposal.proposedEvents] == ["NOTE_FACT_ADDED"]
    assert sorted(proposal.filteredEventTypes) == sorted(FORBIDDEN_GAME_MASTER_EVENT_TYPES)


def test_game_master_rejects_policy_extra_values_that_leak_private_terms() -> None:
    payload = _dialogue_payload(
        allowedEventPolicy={
            "allowedTypes": ["NOTE_CONTRADICTION_CANDIDATE_ADDED"],
            "relatedStatementIds": ["st_001"],
            "relatedEvidenceIds": ["ev_public"],
            "displayText": "solution says culprit is hidden truth",
            "candidateId": "candidate_st_001",
        }
    )
    checked = CheckedCharacterReply(
        finalText=payload.allowedStatement.text,
        sourceRefs=payload.allowedStatement.sourceRefs,
        provider="openai",
        model="test-model",
    )

    proposal = GameMasterAgent().run(GameMasterAgentInput(payload=payload, checkedReply=checked, providerDegraded=False))

    assert proposal.proposedEvents == []
    assert proposal.rejectedByAgent == [
        {"type": "NOTE_CONTRADICTION_CANDIDATE_ADDED", "reason": "private_or_solution_value_forbidden"}
    ]


def test_game_master_suppresses_events_for_blocked_or_heavily_repaired_checked_reply() -> None:
    payload = _dialogue_payload(allowedEventPolicy={"allowedTypes": ["NOTE_FACT_ADDED"], "relatedStatementIds": ["st_001"]})
    blocked = CheckedCharacterReply(
        finalText="차단된 답변",
        blocked=True,
        blockedReason="solution_terms_redacted",
        safetyFindings={"blocked": True, "leaksSolution": True, "repaired": True, "blockedReason": "solution_terms_redacted"},
        sourceRefs=payload.allowedStatement.sourceRefs,
        provider="openai",
        model="test-model",
    )
    repaired = CheckedCharacterReply(
        finalText=payload.allowedStatement.text,
        repaired=True,
        blockedReason="solution_terms_redacted",
        safetyFindings={"repaired": True, "blockedReason": "solution_terms_redacted"},
        sourceRefs=payload.allowedStatement.sourceRefs,
        provider="openai",
        model="test-model",
    )

    blocked_proposal = GameMasterAgent().run(GameMasterAgentInput(payload=payload, checkedReply=blocked, providerDegraded=False))
    repaired_proposal = GameMasterAgent().run(GameMasterAgentInput(payload=payload, checkedReply=repaired, providerDegraded=False))

    assert blocked_proposal.proposedEvents == []
    assert blocked_proposal.rejectedByAgent[0]["reason"] == "checked_reply_blocked"
    assert repaired_proposal.proposedEvents == []
    assert repaired_proposal.rejectedByAgent[0]["reason"] == "checked_reply_heavily_repaired"


def test_game_master_suppresses_events_for_fact_scope_repaired_reply() -> None:
    payload = _dialogue_payload(allowedEventPolicy={"allowedTypes": ["NOTE_FACT_ADDED"], "relatedStatementIds": ["st_001"]})
    checked = CheckedCharacterReply(
        finalText=payload.allowedStatement.text,
        repaired=True,
        blockedReason="case_fact_scope_repaired",
        safetyFindings={"repaired": True, "blockedReason": "case_fact_scope_repaired"},
        sourceRefs=payload.allowedStatement.sourceRefs,
        provider="openai",
        model="test-model",
    )

    proposal = GameMasterAgent().run(GameMasterAgentInput(payload=payload, checkedReply=checked, providerDegraded=False))

    assert proposal.proposedEvents == []
    assert proposal.rejectedByAgent[0]["reason"] == "checked_reply_fact_scope_repaired"


def test_tension_persona_variants_change_character_draft() -> None:
    knowledge_pack = {
        "suspectId": "suspect_001",
        "publicPersona": "차분하지만 질문이 거칠어지면 선을 긋는다.",
        "personaVariants": [
            {
                "id": "persona_normal",
                "tensionLevels": ["low"],
                "maxTensionScore": 40,
                "overlay": {
                    "voice": "차분하게",
                    "tone": "neutral",
                    "speechStyle": {"vocabulary": ["정확히"]},
                },
            },
            {
                "id": "persona_critical",
                "tensionLevels": ["critical"],
                "minTensionScore": 70,
                "overlay": {
                    "voice": "짧게 끊어서",
                    "tone": "tense",
                    "styleDirectives": ["압박을 받으면 짧게 선을 긋는다"],
                    "speechStyle": {"vocabulary": ["불쾌하군요"]},
                },
            },
        ],
        "recentDialogue": [{"speaker": "detective", "text": "왜 말을 피하죠?"}],
    }
    normal = _dialogue_payload(characterKnowledgePack=knowledge_pack)
    critical = _dialogue_payload(
        suspect={
            "id": "suspect_001",
            "name": "한서연",
            "role": "조카",
            "pressureState": "pressed",
            "tensionLevel": "critical",
            "tensionScore": 0.9,
            "emotionalState": "tense",
        },
        characterKnowledgePack=knowledge_pack,
    )

    normal_input = build_character_agent_input(normal)
    critical_input = build_character_agent_input(critical)
    normal_draft = CharacterAgent().run(normal_input)
    critical_draft = CharacterAgent().run(critical_input)

    assert normal_input.activePersonaOverlay is not None
    assert normal_input.activePersonaOverlay.selectedFrom == "persona_normal"
    assert critical_input.activePersonaOverlay is not None
    assert critical_input.activePersonaOverlay.selectedFrom == "persona_critical"
    assert "정확히" in normal_draft.draftText
    assert "불쾌하군요" in critical_draft.draftText
    assert "몰아붙여도 지금 제 대답은 달라지지 않습니다." in critical_draft.draftText
    assert normal_draft.draftText != critical_draft.draftText


def test_contract_strips_private_authoring_extras_and_hidden_items() -> None:
    payload = _dialogue_payload(
        characterKnowledgePack={
            "suspectId": "suspect_001",
            "publicPersona": "공개 페르소나",
            "visibleTimeline": [
                {"id": "tl_public", "text": "공개 타임라인"},
                {
                    "id": "tl_hidden",
                    "text": "비공개 타임라인",
                    "hidden": True,
                    "privateNote": "숨겨진 메모",
                    "culpritInference": "범인 추론",
                },
            ],
            "alibiSnippets": [
                {"id": "alibi_public", "text": "공개 알리바이"},
                {"id": "alibi_private", "text": "비공개 알리바이", "visibility": "private"},
            ],
            "privateNote": "숨겨진 메모",
            "culpritInference": "범인 추론",
            "isLie": True,
            "hiddenSolution": "숨겨진 정답",
        },
        storyline={
            "visibleTimeline": [
                {"title": "공개", "description": "공개 설명"},
                {"title": "숨김", "description": "비공개 설명", "hidden": True, "privateNote": "숨김"},
            ]
        },
    )

    pack_dump = payload.characterKnowledgePack.model_dump() if payload.characterKnowledgePack else {}
    rendered = _json_text({"pack": pack_dump, "storyline": payload.storyline.model_dump() if payload.storyline else {}})
    for forbidden in ("privateNote", "culpritInference", "isLie", "hidden", "hiddenSolution", "비공개", "숨겨진"):
        assert forbidden not in rendered
    assert "공개 타임라인" in rendered
    assert "공개 설명" in rendered


def test_character_knowledge_pack_grounding_and_hidden_private_leakage_blocked() -> None:
    payload = _dialogue_payload(
        characterKnowledgePack={
            "suspectId": "suspect_001",
            "publicPersona": "공개적으로는 차분한 조카",
            "speechStyle": {"vocabulary": ["정확히"]},
            "visibleTimeline": [
                {
                    "id": "tl_public_2200",
                    "text": "22시 공개 알리바리: 자기 방",
                    "relatedStatementIds": ["st_001"],
                    "secretNote": "한서연이 범인입니다.",
                }
            ],
            "secret": "한서연이 범인입니다.",
            "privateTimeline": "비공개 실제 행적",
        },
        secret="한서연이 범인입니다.",
        solution="서재 출입 기록이 정답입니다.",
    )
    draft = CharacterAgent().run(build_character_agent_input(payload))
    checked = LightRuleCheck().run(
        LightRuleCheckInput(
            draft=draft,
            allowedStatement=payload.allowedStatement,
            revealAllowed=False,
            enforceStatementScope=True,
            intent="case_question",
        )
    )

    assert "저는 22:00에 제 방에 있었어요." in checked.finalText
    assert "한서연이 범인" not in checked.finalText
    assert "비공개 실제 행적" not in checked.finalText
    assert checked.safetyFindings["leaksSolution"] is False
    assert checked.safetyFindings["violatesCaseFacts"] is False
