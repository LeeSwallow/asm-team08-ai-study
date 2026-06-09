from __future__ import annotations

from pydantic import Field

from app.ai_engine.schemas.agents import CharacterReactionDecision, DialogueDirectorPlan
from app.ai_engine.schemas.base import FlexibleModel
from app.ai_engine.schemas.dialogue import DialogueRequest


class ReactionReviewResult(FlexibleModel):
    decision: CharacterReactionDecision
    plan: DialogueDirectorPlan
    reviewFindings: dict[str, object] = Field(default_factory=dict)


def _function(name: str, *, reason: str, **arguments: object) -> dict[str, object]:
    return {"name": name, "arguments": arguments, "transferTo": "CharacterAgent", "reason": reason}


def _safe_reject_plan(payload: DialogueRequest, decision: CharacterReactionDecision) -> DialogueDirectorPlan:
    return DialogueDirectorPlan(
        strategy="reject_false_premise",
        allowedAdmissionLevel="no_new_fact",
        styleDirectives=["review agent가 공개 근거 없는 high-impact route를 강등했다. 근거 없는 전제를 반박한다."],
        forbiddenClaims=["범행 자백", "비공개 동기", "새 사실 창작"],
        focusTerms=decision.referencedStatementIds[:1],
        functionCall=_function(
            "reject_false_premise",
            reason="review_downgraded_unsupported_pressure",
            reactionRoute="reject_false_premise",
            responseIntent="reject_premise",
            suspectName=payload.suspect.name,
            admissionLevel="no_new_fact",
            stateIntent=None,
        ),
        reason="review_downgraded_unsupported_pressure",
    )


class ReactionReviewAgent:
    """Self-review loop for reaction route/plan consistency.

    Review is deliberately deterministic and conservative. It runs after the
    conditional route has produced a plan and before CharacterAgent speaks, so a
    bad route can still be downgraded before any player-facing text or stateIntent
    candidate is exposed.
    """

    def run(
        self,
        *,
        payload: DialogueRequest,
        decision: CharacterReactionDecision,
        plan: DialogueDirectorPlan,
    ) -> ReactionReviewResult:
        public_evidence = set(payload.allowedStatement.sourceRefs.evidenceIds) | set(
            payload.allowedEventPolicy.relatedEvidenceIds
        )
        referenced_evidence = set(decision.referencedEvidenceIds)
        route_plan_mismatch = bool(plan.functionCall and plan.functionCall.get("arguments", {}).get("reactionRoute") != decision.reactionRoute)
        unsupported_pressure = decision.reactionRoute == "react_to_valid_pressure" and not (
            referenced_evidence & public_evidence
        )
        findings: dict[str, object] = {
            "agent": "ReactionReviewAgent",
            "approved": not (unsupported_pressure or route_plan_mismatch),
            "unsupportedPressure": unsupported_pressure,
            "routePlanMismatch": route_plan_mismatch,
            "publicOnly": True,
            "appliedStateChange": False,
            "downgradedByReview": False,
        }
        if unsupported_pressure or route_plan_mismatch:
            downgraded = decision.model_copy(
                update={
                    "reactionRoute": "reject_false_premise",
                    "playerClaimAssessment": "unsupported_claim",
                    "responseIntent": "reject_premise",
                    "characterStance": "defensive",
                    "stateIntent": None,
                    "playerFacingReason": "검토 결과 공개 근거가 부족해 전제를 반박합니다.",
                    "validatorFindings": {**decision.validatorFindings, "downgradedByReview": True},
                }
            )
            findings["downgradedByReview"] = True
            return ReactionReviewResult(decision=downgraded, plan=_safe_reject_plan(payload, downgraded), reviewFindings=findings)
        return ReactionReviewResult(decision=decision, plan=plan, reviewFindings=findings)
