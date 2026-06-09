from __future__ import annotations

from app.ai_engine.agents.reaction_librarian_agent import ReactionLibrarianAgent
from app.ai_engine.agents.reaction_review_agent import ReactionReviewAgent
from app.ai_engine.graph.dialogue_generation_nodes import build_react_to_valid_pressure_plan
from app.ai_engine.schemas.agents import CharacterReactionDecision
from app.ai_engine.schemas.dialogue import DialogueRequest


def _request() -> DialogueRequest:
    return DialogueRequest.model_validate(
        {
            "requestId": "req_review",
            "sessionId": "sess_review",
            "caseId": "case_001",
            "suspect": {"id": "char_hanseoyeon", "name": "한서연"},
            "question": {"id": "q", "text": "와인잔 립스틱 자국이 네 진술이랑 안 맞는데?"},
            "allowedStatement": {
                "id": "stmt_visible_hanseoyeon",
                "text": "한서연은 사건 당일 응접실에 있었다고 진술했다.",
                "sourceRefs": {"statementIds": ["stmt_visible_hanseoyeon"], "evidenceIds": [], "timelineIds": []},
            },
            "style": {"tone": "tense", "maxLength": 220},
        }
    )


def test_review_agent_downgrades_high_impact_route_without_public_evidence() -> None:
    payload = _request()
    decision = CharacterReactionDecision(
        suspectId="char_hanseoyeon",
        reactionRoute="react_to_valid_pressure",
        playerClaimAssessment="valid_pressure",
        responseIntent="acknowledge_conflict_without_confession",
        referencedEvidenceIds=[],
        stateIntent={"type": "raise_pressure_intent", "appliedStateChange": False},
    )
    plan = build_react_to_valid_pressure_plan({"payload": payload, "character_reaction_decision": decision})[
        "dialogue_director_plan"
    ]

    reviewed = ReactionReviewAgent().run(payload=payload, decision=decision, plan=plan)

    assert reviewed.decision.reactionRoute == "reject_false_premise"
    assert reviewed.decision.stateIntent is None
    assert reviewed.plan.strategy == "reject_false_premise"
    assert reviewed.reviewFindings["approved"] is False
    assert reviewed.reviewFindings["downgradedByReview"] is True


def test_librarian_agent_records_public_route_card_without_private_payload() -> None:
    payload = _request()
    decision = CharacterReactionDecision(
        suspectId="char_hanseoyeon",
        reactionRoute="reject_false_premise",
        playerClaimAssessment="unsupported_claim",
        responseIntent="reject_premise",
        confidence=0.84,
        rationale="internal rationale should not be player copy",
        playerFacingReason="근거 없는 단정이라 캐릭터가 전제를 반박합니다.",
    )

    card = ReactionLibrarianAgent().run(payload=payload, decision=decision, review_findings={"approved": True})

    assert card["route"] == "reject_false_premise"
    assert card["label"] == "근거 없는 단정"
    assert card["publicOnly"] is True
    assert card["appliedStateChange"] is False
    assert "internal rationale" not in str(card)
