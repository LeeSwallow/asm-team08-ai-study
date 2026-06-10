from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from app.domain.models import Case, SessionState
from app.domain.text_matcher import evidence_is_mentioned


InterrogationMove = Literal[
    "ask_case_fact",
    "ask_timeline",
    "present_evidence",
    "press_inconsistency",
    "repeat_pressure",
    "small_talk",
    "unmatched",
]


def clamp_pressure(value: int | float | None) -> int:
    return max(0, min(100, int(value or 0)))


def pressure_state(pressure: int | float | None) -> str:
    score = clamp_pressure(pressure)
    if score >= 75:
        return "broken"
    if score >= 32:
        return "pressed"
    return "normal"


def emotional_state(pressure: int | float | None) -> str:
    score = clamp_pressure(pressure)
    if score >= 75:
        return "breakdown"
    if score >= 52:
        return "shocked"
    if score >= 32:
        return "defensive"
    if score >= 16:
        return "wary"
    return "neutral"


def tension_level(pressure: int | float | None) -> str:
    score = clamp_pressure(pressure)
    if score >= 75:
        return "critical"
    if score >= 52:
        return "high"
    if score >= 32:
        return "medium"
    return "low"


def composure_state(pressure: int | float | None) -> str:
    score = clamp_pressure(pressure)
    if score >= 75:
        return "broken"
    if score >= 58:
        return "breaking"
    if score >= 38:
        return "rattled"
    if score >= 16:
        return "guarded"
    return "calm"


def disclosure_stage(
    pressure: int | float | None,
    discovered_contradiction_count: int = 0,
    has_core_contradiction: bool = False,
) -> str:
    score = clamp_pressure(pressure)
    # public_break: core 포함 2개+, 또는 3개+, 또는 압박 70+
    if (has_core_contradiction and discovered_contradiction_count >= 2) or discovered_contradiction_count >= 3 or score >= 70:
        return "public_break"
    # forced_explanation: 2개+, 또는 압박 55+
    if discovered_contradiction_count >= 2 or score >= 55:
        return "forced_explanation"
    # partial_admission: 1개+, 또는 압박 35+
    if discovered_contradiction_count >= 1 or score >= 35:
        return "partial_admission"
    if score >= 15:
        return "deflection"
    return "denial"


def pressure_for_stage(stage: str) -> int:
    """Compatibility score for existing UI/API surfaces; not a transition rule."""
    return {
        "denial": 0,
        "deflection": 12,
        "partial_admission": 30,
        "forced_explanation": 50,
        "public_break": 72,
    }.get(stage, 0)


def visual_expression(pressure: int | float | None) -> str:
    return emotional_state(pressure)


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def _source_mentioned(normalized_message: str, *texts: str | None) -> bool:
    compact = normalized_message.replace(" ", "")
    for text in texts:
        normalized = _normalize_text(text)
        if not normalized:
            continue
        pieces = [piece for piece in re.split(r"[^0-9a-zA-Z가-힣]+", normalized) if len(piece) >= 2]
        if any(piece in compact for piece in pieces):
            return True
    return False


def _visible_evidence_ids_mentioned(case: Case, session: SessionState, player_message: str) -> list[str]:
    normalized = _normalize_text(player_message)
    mentioned: list[str] = []
    for evidence in case.evidence:
        if evidence.evidenceId not in session.unlockedEvidenceIds:
            continue
        if evidence_is_mentioned(normalized, evidence):
            mentioned.append(evidence.evidenceId)
    return list(dict.fromkeys(mentioned))


def _move_for(dialogue_mode: str | None, consumed_question: bool, related_contradiction_ids: list[str]) -> InterrogationMove:
    if dialogue_mode == "small_talk":
        return "small_talk"
    if dialogue_mode == "pressure_followup":
        return "repeat_pressure"
    if related_contradiction_ids:
        return "press_inconsistency"
    if dialogue_mode == "timeline_question":
        return "ask_timeline"
    if dialogue_mode == "evidence_question":
        return "press_inconsistency" if related_contradiction_ids else "present_evidence"
    if dialogue_mode == "unmatched":
        return "unmatched"
    if consumed_question:
        return "ask_case_fact"
    return "unmatched"


def suspect_discovered_contradiction_ids(case: Case, session: SessionState, suspect_id: str) -> list[str]:
    known = set(session.discoveredContradictionIds)
    return [
        contradiction.contradictionId
        for contradiction in case.contradictions
        if contradiction.relatedCharacterId == suspect_id and contradiction.contradictionId in known
    ]


def suspect_has_core_contradiction(case: Case, contradiction_ids: list[str]) -> bool:
    known = set(contradiction_ids)
    return any(
        contradiction.severity == "core" and contradiction.contradictionId in known
        for contradiction in case.contradictions
    )


def stage_from_contradictions(case: Case, session: SessionState, suspect_id: str) -> str:
    contradiction_ids = suspect_discovered_contradiction_ids(case, session, suspect_id)
    return disclosure_stage(
        pressure_for_stage("denial"),
        discovered_contradiction_count=len(contradiction_ids),
        has_core_contradiction=suspect_has_core_contradiction(case, contradiction_ids),
    )


@dataclass
class InterrogationTurnResult:
    suspect_id: str
    move: InterrogationMove
    trigger: str
    from_pressure: int
    to_pressure: int
    pressure_delta: int = 0
    pressure_state: str = "normal"
    tension_level: str = "low"
    emotional_state: str = "neutral"
    composure: str = "calm"
    disclosure_stage: str = "denial"
    decisive_evidence: bool = False
    evidence_ids: list[str] = field(default_factory=list)
    statement_ids: list[str] = field(default_factory=list)
    contradiction_ids: list[str] = field(default_factory=list)
    newly_discovered_contradiction_ids: list[str] = field(default_factory=list)
    response_strategy: str = "answer_visible_fact"
    reason: str = "no_state_change"

    def model_dump(self) -> dict[str, Any]:
        return {
            "suspectId": self.suspect_id,
            "move": self.move,
            "trigger": self.trigger,
            "fromPressure": self.from_pressure,
            "toPressure": self.to_pressure,
            "pressureDelta": self.pressure_delta,
            "pressureState": self.pressure_state,
            "tensionLevel": self.tension_level,
            "emotionalState": self.emotional_state,
            "composure": self.composure,
            "disclosureStage": self.disclosure_stage,
            "decisiveEvidence": self.decisive_evidence,
            "evidenceIds": self.evidence_ids,
            "statementIds": self.statement_ids,
            "contradictionIds": self.contradiction_ids,
            "newlyDiscoveredContradictionIds": self.newly_discovered_contradiction_ids,
            "responseStrategy": self.response_strategy,
            "reason": self.reason,
        }


def build_interrogation_snapshot(session: SessionState, suspect_id: str, case: Case | None = None) -> dict[str, Any]:
    if case is not None:
        suspect_contradictions = suspect_discovered_contradiction_ids(case, session, suspect_id)
        stage = stage_from_contradictions(case, session, suspect_id)
        pressure = max(clamp_pressure(session.pressureBySuspect.get(suspect_id, 0)), pressure_for_stage(stage))
    else:
        pressure = clamp_pressure(session.pressureBySuspect.get(suspect_id, 0))
        suspect_contradictions = list(session.discoveredContradictionIds)
        stage = disclosure_stage(pressure, len(suspect_contradictions))
    return {
        "suspectId": suspect_id,
        "pressure": pressure,
        "pressureState": pressure_state(pressure),
        "tensionLevel": tension_level(pressure),
        "emotionalState": emotional_state(pressure),
        "composure": composure_state(pressure),
        "disclosureStage": stage,
        "discoveredContradictionIds": suspect_contradictions,
    }


def transition_interrogation_state(
    *,
    case: Case,
    session: SessionState,
    suspect_id: str,
    dialogue_mode: str | None,
    consumed_question: bool,
    player_message: str,
    allowed_statement: dict[str, Any],
    allowed_event_policy: dict[str, Any],
) -> InterrogationTurnResult:
    related_contradiction_ids = list(allowed_event_policy.get("relatedContradictionIds") or [])
    move = _move_for(dialogue_mode, consumed_question, related_contradiction_ids)
    before_stage = stage_from_contradictions(case, session, suspect_id)
    before = max(clamp_pressure(session.pressureBySuspect.get(suspect_id, 0)), pressure_for_stage(before_stage))
    previous_contradiction_count = len(suspect_discovered_contradiction_ids(case, session, suspect_id))
    evidence_ids = _visible_evidence_ids_mentioned(case, session, player_message)
    statement_ids = list(allowed_event_policy.get("relatedStatementIds") or [])
    if move == "ask_case_fact" and evidence_ids:
        move = "present_evidence"
    newly_discovered: list[str] = []
    turn_contradiction_ids: list[str] = []
    decisive = False
    reason = "state_observed"

    if move in {"present_evidence", "press_inconsistency"} or related_contradiction_ids:
        visible_statements = set(session.unlockedStatementIds)
        visible_evidence = set(session.unlockedEvidenceIds)
        normalized = _normalize_text(player_message)
        for contradiction in case.contradictions:
            if contradiction.relatedCharacterId != suspect_id:
                continue
            if related_contradiction_ids and contradiction.contradictionId not in related_contradiction_ids:
                continue
            if not set(contradiction.requiredStatementIds).issubset(visible_statements):
                continue
            if not set(contradiction.requiredEvidenceIds).issubset(visible_evidence):
                continue
            presented = any(
                evidence.evidenceId in evidence_ids
                or evidence_is_mentioned(normalized, evidence)
                for evidence in case.evidence
                if evidence.evidenceId in contradiction.requiredEvidenceIds
            )
            if not presented:
                continue
            decisive = True
            if contradiction.contradictionId not in session.discoveredContradictionIds:
                session.discoveredContradictionIds.append(contradiction.contradictionId)
                newly_discovered.append(contradiction.contradictionId)
                reason = "decisive_visible_evidence"
            else:
                reason = "known_contradiction_pressed_again"
            related_contradiction_ids.append(contradiction.contradictionId)
            turn_contradiction_ids.append(contradiction.contradictionId)
            statement_ids.extend(contradiction.requiredStatementIds)
            evidence_ids.extend(contradiction.requiredEvidenceIds)

    suspect_contradiction_ids = suspect_discovered_contradiction_ids(case, session, suspect_id)
    contradiction_count = len(suspect_contradiction_ids)
    stage = stage_from_contradictions(case, session, suspect_id)
    if decisive and contradiction_count == previous_contradiction_count and before_stage in {"denial", "deflection", "partial_admission"}:
        stage = "forced_explanation"

    if move == "repeat_pressure" and not decisive:
        if before_stage in {"partial_admission", "forced_explanation", "public_break"}:
            stage = "forced_explanation"
        else:
            stage = "deflection"
        reason = "player_pressed_previous_answer"
    elif move == "present_evidence" and not decisive and evidence_ids and before < pressure_for_stage("deflection"):
        stage = "deflection"
        reason = "non_decisive_evidence_presented"

    after = max(before, pressure_for_stage(stage))
    if after != before:
        session.pressureBySuspect[suspect_id] = after

    refs = allowed_statement.setdefault("sourceRefs", {})
    refs["contradictionIds"] = list(dict.fromkeys([*(refs.get("contradictionIds") or []), *turn_contradiction_ids]))
    refs["evidenceIds"] = list(dict.fromkeys([*(refs.get("evidenceIds") or []), *evidence_ids]))
    refs["statementIds"] = list(dict.fromkeys([*(refs.get("statementIds") or []), *statement_ids]))
    refs["timelineIds"] = list(
        dict.fromkeys([*(refs.get("timelineIds") or []), *(allowed_event_policy.get("relatedTimelineEventIds") or [])])
    )
    allowed_event_policy["relatedContradictionIds"] = list(dict.fromkeys(related_contradiction_ids))
    allowed_event_policy["relatedEvidenceIds"] = list(dict.fromkeys([*(allowed_event_policy.get("relatedEvidenceIds") or []), *evidence_ids]))
    allowed_event_policy["relatedStatementIds"] = list(dict.fromkeys([*(allowed_event_policy.get("relatedStatementIds") or []), *statement_ids]))

    response_strategy = "answer_visible_fact"
    if decisive:
        response_strategy = "stagger_then_address_evidence"
    elif after >= 70:
        response_strategy = "stop_evasion_and_disclose_visible_scope"
    elif move == "repeat_pressure":
        response_strategy = "push_back_without_requesting_clues"
    elif move == "present_evidence":
        response_strategy = "react_to_evidence_without_new_claims"

    return InterrogationTurnResult(
        suspect_id=suspect_id,
        move=move,
        trigger=str(dialogue_mode or "unknown"),
        from_pressure=before,
        to_pressure=after,
        pressure_delta=after - before,
        pressure_state=pressure_state(after),
        tension_level=tension_level(after),
        emotional_state=emotional_state(after),
        composure=composure_state(after),
        disclosure_stage=stage,
        decisive_evidence=decisive,
        evidence_ids=list(dict.fromkeys(evidence_ids)),
        statement_ids=list(dict.fromkeys(statement_ids)),
        contradiction_ids=list(dict.fromkeys(turn_contradiction_ids)),
        newly_discovered_contradiction_ids=newly_discovered,
        response_strategy=response_strategy,
        reason=reason,
    )
