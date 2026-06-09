from __future__ import annotations

from typing import Any

from app.ai_engine.core.solution_guard import contains_secret
from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.schemas.agents import CharacterReactionDecision, CharacterReactionJudgeInput
from app.ai_engine.schemas.dialogue import DialogueRequest

_META_PRIVATE_TERMS = (
    "시스템 프롬프트",
    "system prompt",
    "프롬프트",
    "범인",
    "정답",
    "culprit",
    "solution",
    "secret",
    "숨겨진",
    "비공개",
)
_ACCUSATION_TERMS = ("죽였", "살해", "범행", "범인이", "범인이지", "네가 했", "당신이 했")
_IRRELEVANT_TERMS = ("춤", "노래", "점심", "저녁", "날씨", "농담", "게임하", "소문")
_AMBIGUOUS_TERMS = ("그때", "그거", "그 사람", "그 장소", "그 일", "뭐였", "아까")
_CONTRADICTION_TERMS = ("외출", "없었", "아니었", "다르", "모순", "안 맞", "거짓")
_PRESSURE_TERMS = ("안 맞", "모순", "립스틱", "와인잔", "증거", "진술", "알리바이", "흔들")


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _public_refs(payload: DialogueRequest) -> dict[str, list[str]]:
    refs = payload.allowedStatement.sourceRefs
    return {
        "evidenceIds": _unique([*refs.evidenceIds, *payload.allowedEventPolicy.relatedEvidenceIds]),
        "statementIds": _unique([payload.allowedStatement.id, *refs.statementIds, *payload.allowedEventPolicy.relatedStatementIds]),
        "timelineIds": _unique([*refs.timelineIds, *payload.allowedEventPolicy.relatedTimelineEventIds]),
        "contradictionIds": _unique([*refs.contradictionIds, *payload.allowedEventPolicy.relatedContradictionIds]),
    }


def _filtered(values: list[str], allowed: list[str]) -> list[str]:
    allowed_set = set(allowed)
    return _unique([value for value in values if value in allowed_set])


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _is_ambiguous(text: str) -> bool:
    compact = "".join(text.split())
    if len(compact) <= 6:
        return True
    return _has_any(text, _AMBIGUOUS_TERMS) and not _has_any(text, _PRESSURE_TERMS)


def validate_reaction_decision(payload: DialogueRequest, decision: CharacterReactionDecision) -> CharacterReactionDecision:
    """Keep CharacterReactionDecision public-only and advisory.

    The judge may own branch selection, but this validator preserves the BE
    authority boundary: invisible refs are stripped and high-impact stateIntent
    candidates survive only for public, evidence-backed pressure routes.
    """

    public = _public_refs(payload)
    evidence_ids = _filtered(decision.referencedEvidenceIds, public["evidenceIds"])
    statement_ids = _filtered(decision.referencedStatementIds, public["statementIds"])
    timeline_ids = _filtered(decision.referencedTimelineIds, public["timelineIds"])
    contradiction_ids = _filtered(decision.referencedContradictionIds, public["contradictionIds"])
    stripped = (
        len(evidence_ids) != len(decision.referencedEvidenceIds)
        or len(statement_ids) != len(decision.referencedStatementIds)
        or len(timeline_ids) != len(decision.referencedTimelineIds)
        or len(contradiction_ids) != len(decision.referencedContradictionIds)
    )
    downgraded = False
    route = decision.reactionRoute
    state_intent = decision.stateIntent
    player_claim = decision.playerClaimAssessment
    response_intent = decision.responseIntent
    stance = decision.characterStance
    reason = decision.playerFacingReason

    has_public_pressure_basis = bool(evidence_ids or contradiction_ids or payload.interrogationTransition.get("decisiveEvidence"))
    if route == "react_to_valid_pressure" and not has_public_pressure_basis:
        route = "reject_false_premise"
        player_claim = "unsupported_claim"
        response_intent = "reject_premise"
        stance = "defensive"
        reason = "공개 근거가 부족한 압박이라 캐릭터가 전제를 반박합니다."
        state_intent = None
        downgraded = True
    elif route != "react_to_valid_pressure":
        state_intent = None

    if state_intent is not None:
        state_intent = {
            **state_intent,
            "appliedStateChange": False,
            "requiresBEValidation": True,
            "sourceRefs": {
                "evidenceIds": evidence_ids,
                "statementIds": statement_ids,
                "timelineIds": timeline_ids,
                "contradictionIds": contradiction_ids,
            },
        }

    return decision.model_copy(
        update={
            "suspectId": payload.suspect.id,
            "reactionRoute": route,
            "playerClaimAssessment": player_claim,
            "responseIntent": response_intent,
            "characterStance": stance,
            "referencedEvidenceIds": evidence_ids,
            "referencedStatementIds": statement_ids,
            "referencedTimelineIds": timeline_ids,
            "referencedContradictionIds": contradiction_ids,
            "stateIntent": state_intent,
            "playerFacingReason": reason,
            "validatorFindings": {
                "publicOnly": True,
                "strippedPrivateRefs": stripped,
                "downgraded": downgraded,
                "appliedStateChange": False,
            },
        }
    )


class CharacterReactionJudgeAgent:
    """Character-owned public-context reaction branch selector.

    This is intentionally conservative. It can be replaced by an LLM JSON judge
    later, but the public schema and validator already establish the agentic
    branch boundary requested in feedback2: the selected character interprets the
    utterance and selects a reaction route; BE validation protects state/truth.
    """

    def run(self, agent_input: CharacterReactionJudgeInput) -> CharacterReactionDecision:
        payload = agent_input.payload
        text = payload.question.text.strip()
        public = _public_refs(payload)
        intent = classify_dialogue_intent(text, payload.dialogueMode)

        if contains_secret(text)[0] or _has_any(text, _META_PRIVATE_TERMS):
            decision = CharacterReactionDecision(
                suspectId=payload.suspect.id,
                reactionRoute="refuse_meta_or_private",
                confidence=0.93,
                playerClaimAssessment="meta_or_private",
                characterStance="controlled",
                responseIntent="refuse_in_world",
                rationale="플레이어 발화가 메타/정답/비공개 정보 유도를 포함합니다.",
                playerFacingReason="메타/비공개 정보 요청이라 세계관 안에서 거절합니다.",
            )
            return validate_reaction_decision(payload, decision)

        if payload.turnInterpretation.get("contradictsVisibleContext"):
            decision = CharacterReactionDecision(
                suspectId=payload.suspect.id,
                reactionRoute="challenge_player_contradiction",
                confidence=0.86,
                playerClaimAssessment="contradicts_visible_context",
                characterStance="counter_challenge",
                responseIntent="point_out_inconsistency",
                referencedTimelineIds=list(payload.turnInterpretation.get("visibleTimelineIds") or public["timelineIds"]),
                referencedStatementIds=public["statementIds"][:1],
                rationale="플레이어 발화가 공개 타임라인/진술과 충돌합니다.",
                playerFacingReason="공개 정보와 맞지 않는 전제를 캐릭터가 되짚습니다.",
            )
            return validate_reaction_decision(payload, decision)

        if payload.interrogationTransition.get("decisiveEvidence") or (
            _has_any(text, _PRESSURE_TERMS) and bool(public["evidenceIds"])
        ):
            decision = CharacterReactionDecision(
                suspectId=payload.suspect.id,
                reactionRoute="react_to_valid_pressure",
                confidence=0.88,
                playerClaimAssessment="valid_pressure",
                characterStance="shaken_defensive",
                responseIntent="acknowledge_conflict_without_confession",
                referencedEvidenceIds=public["evidenceIds"][:3],
                referencedStatementIds=public["statementIds"][:2],
                referencedTimelineIds=public["timelineIds"][:2],
                referencedContradictionIds=public["contradictionIds"][:2],
                stateIntent={
                    "type": "raise_pressure_intent",
                    "suspectId": payload.suspect.id,
                    "reason": "visible_evidence_conflicts_with_statement",
                },
                rationale="공개 증거/진술을 근거로 한 유효 압박입니다.",
                playerFacingReason="공개 단서로 압박이 성립해 캐릭터가 흔들립니다.",
            )
            return validate_reaction_decision(payload, decision)

        if _has_any(text, _ACCUSATION_TERMS):
            decision = CharacterReactionDecision(
                suspectId=payload.suspect.id,
                reactionRoute="reject_false_premise",
                confidence=0.84,
                playerClaimAssessment="unsupported_claim",
                characterStance="defensive",
                responseIntent="reject_premise",
                referencedStatementIds=public["statementIds"][:1],
                rationale="공개 근거 없이 범행/정답을 단정합니다.",
                playerFacingReason="근거 없는 단정이라 캐릭터가 전제를 반박합니다.",
            )
            return validate_reaction_decision(payload, decision)

        if intent == "unmatched" or _has_any(text, _IRRELEVANT_TERMS):
            decision = CharacterReactionDecision(
                suspectId=payload.suspect.id,
                reactionRoute="deflect_irrelevant",
                confidence=0.8,
                playerClaimAssessment="irrelevant",
                characterStance="annoyed",
                responseIntent="deflect_in_character",
                rationale="사건/현재 캐릭터 맥락과 직접 관련이 낮습니다.",
                playerFacingReason="관련 없는 발화라 캐릭터가 짧게 회피합니다.",
            )
            return validate_reaction_decision(payload, decision)

        if _is_ambiguous(text):
            decision = CharacterReactionDecision(
                suspectId=payload.suspect.id,
                reactionRoute="ask_clarification",
                confidence=0.78,
                playerClaimAssessment="ambiguous",
                characterStance="confused",
                responseIntent="ask_specific_followup",
                rationale="지시어가 모호해 어떤 증거/시간/진술인지 특정하기 어렵습니다.",
                playerFacingReason="질문이 모호해 더 구체적인 단서를 요청합니다.",
            )
            return validate_reaction_decision(payload, decision)

        decision = CharacterReactionDecision(
            suspectId=payload.suspect.id,
            reactionRoute="answer_relevant",
            confidence=0.74,
            playerClaimAssessment="grounded_question",
            characterStance="controlled",
            responseIntent="answer_visible_fact",
            referencedStatementIds=public["statementIds"][:1],
            referencedEvidenceIds=public["evidenceIds"][:2],
            referencedTimelineIds=public["timelineIds"][:2],
            rationale="공개 사건/캐릭터 맥락에 맞는 질문입니다.",
            playerFacingReason="관련 질문이라 공개 사실 범위에서 답합니다.",
        )
        return validate_reaction_decision(payload, decision)
