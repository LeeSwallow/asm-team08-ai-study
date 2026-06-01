from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.domain.case_engine import visible_timeline
from app.domain.models import Case, SessionState
from app.domain.text_matcher import (
    evidence_is_mentioned,
    meaningful_tokens,
    normalize_text,
    overlap_score,
    text_tokens,
)


def _normalize(value: str | None) -> str:
    return normalize_text(value)


def _tokens(value: str | None) -> set[str]:
    return text_tokens(value)


def _overlap_score(message: str, *texts: str | None) -> int:
    return overlap_score(message, *texts)


def _timeline_id(item: dict[str, Any]) -> str:
    return str(item.get("timelineId") or item.get("sourceId") or f"{item.get('time', '')}:{item.get('title', '')}")


@dataclass
class TurnInterpretation:
    intent: str
    mentioned_evidence_ids: list[str] = field(default_factory=list)
    mentioned_statement_ids: list[str] = field(default_factory=list)
    matched_timeline_ids: list[str] = field(default_factory=list)
    candidate_contradiction_ids: list[str] = field(default_factory=list)
    focus_terms: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def model_dump(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "mentionedEvidenceIds": self.mentioned_evidence_ids,
            "mentionedStatementIds": self.mentioned_statement_ids,
            "matchedTimelineIds": self.matched_timeline_ids,
            "candidateContradictionIds": self.candidate_contradiction_ids,
            "focusTerms": self.focus_terms,
            "confidence": self.confidence,
        }


def interpret_turn(
    *,
    case: Case,
    session: SessionState,
    suspect_id: str,
    player_message: str,
    dialogue_mode: str | None,
) -> TurnInterpretation:
    visible_evidence = set(session.unlockedEvidenceIds)
    visible_statements = set(session.unlockedStatementIds)
    message = _normalize(player_message)
    compact = message.replace(" ", "")

    mentioned_evidence_ids: list[str] = []
    focus_terms: list[str] = []
    for evidence in case.evidence:
        if evidence.evidenceId not in visible_evidence:
            continue
        if evidence_is_mentioned(message, evidence):
            mentioned_evidence_ids.append(evidence.evidenceId)
            focus_terms.extend(sorted(_tokens(message) & (meaningful_tokens(evidence.name) | meaningful_tokens(evidence.description))))

    mentioned_statement_ids: list[str] = []
    for statement in case.statements:
        if statement.statementId not in visible_statements:
            continue
        if statement.characterId != suspect_id:
            continue
        score = _overlap_score(message, statement.questionText, statement.text, statement.timeWindow, statement.location)
        if score >= 2:
            mentioned_statement_ids.append(statement.statementId)

    matched_timeline_ids: list[str] = []
    visible_source_ids = {*mentioned_evidence_ids, *mentioned_statement_ids}
    for item in visible_timeline(case, session):
        source_id = str(item.get("sourceId") or "")
        if source_id in visible_source_ids or _overlap_score(message, item.get("time"), item.get("title"), item.get("description")) >= 2:
            matched_timeline_ids.append(_timeline_id(item))

    candidate_contradiction_ids: list[str] = []
    evidence_set = set(mentioned_evidence_ids)
    statement_set = set(mentioned_statement_ids)
    for contradiction in case.contradictions:
        if contradiction.relatedCharacterId != suspect_id:
            continue
        if not set(contradiction.requiredEvidenceIds).issubset(visible_evidence):
            continue
        if not set(contradiction.requiredStatementIds).issubset(visible_statements):
            continue
        evidence_hit = bool(evidence_set & set(contradiction.requiredEvidenceIds))
        statement_hit = bool(statement_set & set(contradiction.requiredStatementIds))
        if evidence_hit and (statement_hit or dialogue_mode == "evidence_question"):
            candidate_contradiction_ids.append(contradiction.contradictionId)

    if candidate_contradiction_ids:
        intent = "press_inconsistency"
    elif mentioned_evidence_ids:
        intent = "present_evidence"
    elif dialogue_mode == "timeline_question" or any(term in compact for term in ("22시", "10시", "시간", "행적", "알리바이")):
        intent = "ask_timeline"
    elif dialogue_mode == "small_talk":
        intent = "small_talk"
    else:
        intent = dialogue_mode or "ask_case_fact"

    confidence = 0.2
    if mentioned_evidence_ids:
        confidence += 0.25
    if mentioned_statement_ids:
        confidence += 0.2
    if matched_timeline_ids:
        confidence += 0.15
    if candidate_contradiction_ids:
        confidence += 0.25

    return TurnInterpretation(
        intent=intent,
        mentioned_evidence_ids=list(dict.fromkeys(mentioned_evidence_ids)),
        mentioned_statement_ids=list(dict.fromkeys(mentioned_statement_ids)),
        matched_timeline_ids=list(dict.fromkeys(matched_timeline_ids)),
        candidate_contradiction_ids=list(dict.fromkeys(candidate_contradiction_ids)),
        focus_terms=list(dict.fromkeys(focus_terms)),
        confidence=min(1.0, confidence),
    )
