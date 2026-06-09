from __future__ import annotations

from app.ai_engine.schemas.agents import CharacterReactionDecision
from app.ai_engine.schemas.dialogue import DialogueRequest

_ROUTE_LABELS = {
    "answer_relevant": "관련 질문",
    "deflect_irrelevant": "관련 없는 발화",
    "reject_false_premise": "근거 없는 단정",
    "challenge_player_contradiction": "플레이어 발화 모순",
    "react_to_valid_pressure": "유효한 압박",
    "ask_clarification": "모호한 질문",
    "refuse_meta_or_private": "메타/비공개 요청",
}

_ROUTE_EFFECTS = {
    "answer_relevant": "공개 사실 범위에서 답변",
    "deflect_irrelevant": "캐릭터답게 회피",
    "reject_false_premise": "전제 반박",
    "challenge_player_contradiction": "공개 정보 기준으로 되짚음",
    "react_to_valid_pressure": "긴장 반응",
    "ask_clarification": "구체화 요청",
    "refuse_meta_or_private": "세계관 안에서 거절",
}


class ReactionLibrarianAgent:
    """Public route-card curator for FE/diagnostics.

    The librarian stores only player-safe route metadata. It intentionally omits
    internal rationale and hidden/private text so FE can expose the branch without
    leaking case solution context.
    """

    def run(
        self,
        *,
        payload: DialogueRequest,
        decision: CharacterReactionDecision,
        review_findings: dict[str, object] | None = None,
    ) -> dict[str, object]:
        route = decision.reactionRoute
        return {
            "owner": decision.owner,
            "suspectId": payload.suspect.id,
            "route": route,
            "reactionRoute": route,
            "label": _ROUTE_LABELS.get(route, route),
            "effect": _ROUTE_EFFECTS.get(route, "분기 반응"),
            "confidence": decision.confidence,
            "playerClaimAssessment": decision.playerClaimAssessment,
            "characterStance": decision.characterStance,
            "responseIntent": decision.responseIntent,
            "playerFacingReason": decision.playerFacingReason,
            "referencedEvidenceIds": decision.referencedEvidenceIds,
            "referencedStatementIds": decision.referencedStatementIds,
            "referencedTimelineIds": decision.referencedTimelineIds,
            "referencedContradictionIds": decision.referencedContradictionIds,
            "review": review_findings or {},
            "publicOnly": True,
            "appliedStateChange": False,
        }
