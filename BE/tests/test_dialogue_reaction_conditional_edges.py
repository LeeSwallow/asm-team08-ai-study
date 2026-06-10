from __future__ import annotations

from dataclasses import dataclass

from app.ai_engine.graph.dialogue_graph import run_dialogue_graph
from app.infra.local_ai_client import _public_runtime_diagnostics
from app.ai_engine.graph.dialogue_generation_nodes import (
    build_deflect_irrelevant_plan,
    build_react_to_valid_pressure_plan,
    select_character_reaction_route,
)
from app.ai_engine.schemas.agents import CharacterReactionDecision
from app.ai_engine.schemas.dialogue import DialogueRequest


@dataclass
class _Retrieved:
    character_context: object | None = None
    event_context: object | None = None


class _Retriever:
    def retrieve_dialogue_context(self, **kwargs):
        return _Retrieved()


def _request(*, message: str, mode: str | None = None, transition: dict | None = None, refs: dict | None = None) -> DialogueRequest:
    return DialogueRequest.model_validate(
        {
            "requestId": "req_graph",
            "sessionId": "sess_graph",
            "caseId": "case_001",
            "dialogueMode": mode,
            "suspect": {"id": "char_hanseoyeon", "name": "한서연", "pressureState": "calm"},
            "question": {"id": "player_graph", "text": message},
            "allowedStatement": {
                "id": "stmt_visible_hanseoyeon",
                "text": "한서연은 사건 당일 10시 무렵 갤러리 응접실에 있었다고 진술했다.",
                "sourceRefs": refs or {"statementIds": ["stmt_visible_hanseoyeon"], "evidenceIds": [], "timelineIds": []},
            },
            "allowedEventPolicy": {
                "relatedEvidenceIds": (refs or {}).get("evidenceIds", []),
                "relatedStatementIds": ["stmt_visible_hanseoyeon"],
            },
            "interrogationTransition": transition or {},
            "style": {"tone": "tense", "maxLength": 220},
        }
    )


def test_route_selector_returns_validated_reaction_route() -> None:
    decision = CharacterReactionDecision(
        suspectId="char_hanseoyeon",
        reactionRoute="refuse_meta_or_private",
        playerClaimAssessment="meta_or_private",
        responseIntent="refuse_in_world",
    )

    assert select_character_reaction_route({"character_reaction_decision": decision}) == "refuse_meta_or_private"


def test_route_node_builds_deflect_function_transition() -> None:
    state = {
        "payload": _request(message="갑자기 춤춰봐요.", mode="unmatched"),
        "character_reaction_decision": CharacterReactionDecision(
            suspectId="char_hanseoyeon",
            reactionRoute="deflect_irrelevant",
            playerClaimAssessment="irrelevant",
            responseIntent="deflect_in_character",
        ),
    }

    plan = build_deflect_irrelevant_plan(state)["dialogue_director_plan"]

    assert plan.strategy == "deflect_irrelevant"
    assert plan.functionCall["name"] == "deflect_irrelevant_turn"
    assert plan.functionCall["transferTo"] == "CharacterAgent"


def test_route_node_builds_valid_pressure_plan_with_advisory_state_intent() -> None:
    state = {
        "payload": _request(
            message="와인잔 립스틱 자국이 네 진술이랑 안 맞는데?",
            transition={"decisiveEvidence": True},
            refs={"statementIds": ["stmt_visible_hanseoyeon"], "evidenceIds": ["ev_lipstick_glass"], "timelineIds": []},
        ),
        "character_reaction_decision": CharacterReactionDecision(
            suspectId="char_hanseoyeon",
            reactionRoute="react_to_valid_pressure",
            playerClaimAssessment="valid_pressure",
            responseIntent="acknowledge_conflict_without_confession",
            referencedEvidenceIds=["ev_lipstick_glass"],
            stateIntent={"type": "raise_pressure_intent", "appliedStateChange": False},
        ),
    }

    plan = build_react_to_valid_pressure_plan(state)["dialogue_director_plan"]

    assert plan.strategy == "react_to_valid_pressure"
    assert plan.allowedAdmissionLevel == "acknowledge_conflict_only"
    assert plan.functionCall["name"] == "acknowledge_public_contradiction"
    assert plan.functionCall["arguments"]["stateIntent"]["appliedStateChange"] is False


def test_dialogue_graph_preserves_route_specific_seed_in_deterministic_fallback() -> None:
    response = run_dialogue_graph(
        _request(message="갑자기 춤춰봐요.", mode="unmatched"),
        _Retriever(),
    )

    assert response.runtimeDiagnostics["characterReactionRoute"] == "deflect_irrelevant"
    assert (
        "장난" in response.text
        or "말에 맞춰줄" in response.text
        or "똑바로" in response.text
        or "이상한 소리" in response.text
    )
    assert response.text != response.statementId
    assert "응접실에 있었다고 진술했다" not in response.text


def test_dialogue_graph_uses_conditional_reaction_route_in_runtime_diagnostics() -> None:
    response = run_dialogue_graph(
        _request(
            message="와인잔 립스틱 자국이 네 진술이랑 안 맞는데?",
            transition={"decisiveEvidence": True},
            refs={"statementIds": ["stmt_visible_hanseoyeon"], "evidenceIds": ["ev_lipstick_glass"], "timelineIds": []},
        ),
        _Retriever(),
    )

    diagnostics = response.runtimeDiagnostics

    assert diagnostics["characterReactionRoute"] == "react_to_valid_pressure"
    assert diagnostics["conditionalRouteOwner"] == "CharacterReactionJudgeAgent"
    assert diagnostics["functionTransition"]["name"] == "acknowledge_public_contradiction"
    assert diagnostics["characterReaction"]["stateIntent"]["appliedStateChange"] is False


def test_public_runtime_diagnostics_exposes_reaction_without_internal_rationale() -> None:
    public = _public_runtime_diagnostics(
        {
            "characterReaction": {
                "owner": "CharacterReactionJudgeAgent",
                "suspectId": "char_hanseoyeon",
                "reactionRoute": "reject_false_premise",
                "confidence": 0.84,
                "playerClaimAssessment": "unsupported_claim",
                "characterStance": "defensive",
                "responseIntent": "reject_premise",
                "playerFacingReason": "근거 없는 단정이라 캐릭터가 전제를 반박합니다.",
                "rationale": "internal chain should not be exposed",
                "referencedEvidenceIds": [],
                "referencedStatementIds": ["stmt_visible_hanseoyeon"],
                "stateIntent": None,
                "validatorFindings": {"publicOnly": True, "appliedStateChange": False},
            }
        }
    )

    assert public["characterReactionRoute"] == "reject_false_premise"
    assert public["conditionalRouteOwner"] == "CharacterReactionJudgeAgent"
    assert public["characterReaction"]["playerFacingReason"] == "근거 없는 단정이라 캐릭터가 전제를 반박합니다."
    assert "rationale" not in public["characterReaction"]
