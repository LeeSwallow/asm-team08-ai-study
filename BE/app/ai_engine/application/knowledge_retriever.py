from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.application.ports import KnowledgeGraphRepositoryPort

logger = logging.getLogger(__name__)

# ── 엔티티 추출용 패턴 ────────────────────────────────────────────────────────

_TIME_PATTERNS = re.compile(
    r"(\d{1,2}:\d{2})|(\d{1,2}시(?:\s*\d{1,2}분)?)"
    r"|(오전|오후|저녁|밤|새벽|낮|아침)"
    r"|(사건\s*(?:당일|직후|직전|전|후))",
    re.IGNORECASE,
)

_LOCATION_TOKENS = (
    "서재", "방", "복도", "주방", "욕실", "거실", "정원", "차고",
    "현관", "계단", "2층", "1층", "3층", "저택", "밖", "외부", "현장",
)

_EVIDENCE_TOKENS = (
    "와인잔", "와인", "립스틱", "자국", "약", "약물", "처방",
    "출입기록", "출입 기록", "회중시계", "유언장", "통화기록", "통화 기록",
    "부검", "정전", "약상자",
)


@dataclass
class QuestionEntities:
    time_expressions: list[str] = field(default_factory=list)
    location_terms: list[str] = field(default_factory=list)
    evidence_terms: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.time_expressions or self.location_terms or self.evidence_terms)


@dataclass
class CharacterRetrievedContext:
    matched_timeline_events: list[dict] = field(default_factory=list)
    matched_evidence: list[dict] = field(default_factory=list)
    matched_statements: list[dict] = field(default_factory=list)
    alibi_summary: str | None = None
    fact_boundary: str = ""
    retrieval_debug: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (
            self.matched_timeline_events
            or self.matched_evidence
            or self.matched_statements
        )


@dataclass
class GameMasterEventContext:
    matched_statement_ids: list[str] = field(default_factory=list)
    matched_evidence_ids: list[str] = field(default_factory=list)
    matched_timeline_ids: list[str] = field(default_factory=list)
    candidate_contradiction_ids: list[str] = field(default_factory=list)
    note_fact_source_refs: dict = field(default_factory=dict)
    retrieval_debug: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (
            self.matched_statement_ids
            or self.matched_evidence_ids
            or self.matched_timeline_ids
            or self.candidate_contradiction_ids
        )


@dataclass
class DialogueRetrievedContext:
    character_context: CharacterRetrievedContext = field(default_factory=CharacterRetrievedContext)
    event_context: GameMasterEventContext = field(default_factory=GameMasterEventContext)
    retrieval_debug: dict = field(default_factory=dict)


# Backward-compatible alias for older imports. New code should use the
# Character/GameMaster-specific context classes above.
RetrievedContext = CharacterRetrievedContext


def extract_question_entities(question_text: str, allowed_statement_text: str = "") -> QuestionEntities:
    combined = f"{question_text} {allowed_statement_text}"

    time_expressions = list({m.group(0) for m in _TIME_PATTERNS.finditer(combined) if m.group(0).strip()})
    location_terms = [tok for tok in _LOCATION_TOKENS if tok in combined]
    evidence_terms = [tok for tok in _EVIDENCE_TOKENS if tok in combined]

    return QuestionEntities(
        time_expressions=time_expressions,
        location_terms=location_terms,
        evidence_terms=evidence_terms,
    )


class KnowledgeRetriever:
    """Neo4j 기반 케이스 지식 검색기. Neo4j 미설정 시 빈 컨텍스트를 반환한다."""

    def __init__(self, graph_repo: KnowledgeGraphRepositoryPort | None = None) -> None:
        self._graph_repo = graph_repo

    @property
    def _available(self) -> bool:
        return self._graph_repo is not None and self._graph_repo.available

    def retrieve_character_context(
        self,
        *,
        case_id: str,
        suspect_id: str,
        question_text: str,
        allowed_statement_text: str,
        unlocked_statement_ids: list[str],
        unlocked_evidence_ids: list[str],
        discovered_contradiction_ids: list[str],
    ) -> CharacterRetrievedContext:
        return self.retrieve_dialogue_context(
            case_id=case_id,
            suspect_id=suspect_id,
            question_text=question_text,
            allowed_statement_text=allowed_statement_text,
            unlocked_statement_ids=unlocked_statement_ids,
            unlocked_evidence_ids=unlocked_evidence_ids,
            discovered_contradiction_ids=discovered_contradiction_ids,
        ).character_context

    def retrieve_event_context(
        self,
        *,
        case_id: str,
        suspect_id: str,
        question_text: str,
        allowed_statement_text: str,
        unlocked_statement_ids: list[str],
        unlocked_evidence_ids: list[str],
        discovered_contradiction_ids: list[str],
    ) -> GameMasterEventContext:
        return self.retrieve_dialogue_context(
            case_id=case_id,
            suspect_id=suspect_id,
            question_text=question_text,
            allowed_statement_text=allowed_statement_text,
            unlocked_statement_ids=unlocked_statement_ids,
            unlocked_evidence_ids=unlocked_evidence_ids,
            discovered_contradiction_ids=discovered_contradiction_ids,
        ).event_context

    def retrieve_dialogue_context(
        self,
        *,
        case_id: str,
        suspect_id: str,
        question_text: str,
        allowed_statement_text: str,
        unlocked_statement_ids: list[str],
        unlocked_evidence_ids: list[str],
        discovered_contradiction_ids: list[str],
    ) -> DialogueRetrievedContext:
        if not self._available:
            return DialogueRetrievedContext(
                character_context=CharacterRetrievedContext(fact_boundary=allowed_statement_text),
                event_context=GameMasterEventContext(),
                retrieval_debug={"neo4j": False},
            )

        entities = extract_question_entities(question_text, allowed_statement_text)
        debug: dict = {
            "entities": {
                "timeExpressions": entities.time_expressions,
                "locationTerms": entities.location_terms,
                "evidenceTerms": entities.evidence_terms,
            },
            "neo4j": True,
        }

        timeline_events: list[dict] = []
        matched_evidence: list[dict] = []
        matched_statements: list[dict] = []
        candidate_contradiction_ids: list[str] = []
        alibi_summary: str | None = None

        try:
            # ① 용의자 + 시간대 → 알리바이 진술 + 충돌 증거
            if entities.time_expressions or suspect_id:
                rows = self._graph_repo.find_alibi_conflicts(
                    case_id=case_id,
                    suspect_id=suspect_id,
                    time_expressions=entities.time_expressions,
                    unlocked_statement_ids=unlocked_statement_ids,
                    discovered_contradiction_ids=discovered_contradiction_ids,
                )
                for row in rows:
                    if row.get("statementText"):
                        matched_statements.append({
                            "id": row["statementId"],
                            "text": row["statementText"],
                            "timeWindow": row.get("timeWindow"),
                            "location": row.get("location"),
                        })
                        # 알리바이 요약 (첫 번째 진술 기준)
                        if alibi_summary is None and row.get("timeWindow"):
                            alibi_summary = f"{row['timeWindow']} {row.get('location', '')} (공개 알리바이)".strip()
                        # 충돌 모순 수집
                        for con in (row.get("contradictions") or []):
                            contradiction_id = con.get("contradictionId")
                            if contradiction_id and contradiction_id not in candidate_contradiction_ids:
                                candidate_contradiction_ids.append(contradiction_id)

            # ② 질문에 언급된 증거 → 관련 모순 탐색
            if entities.evidence_terms and unlocked_evidence_ids:
                rows = self._graph_repo.find_evidence_context(
                    case_id=case_id,
                    evidence_terms=entities.evidence_terms,
                    unlocked_evidence_ids=unlocked_evidence_ids,
                )
                for row in rows:
                    if row.get("name"):
                        matched_evidence.append({
                            "id": row["evidenceId"],
                            "name": row["name"],
                            "description": row.get("description", ""),
                            "timeWindow": row.get("timeWindow"),
                        })
                        for con in (row.get("contradictions") or []):
                            contradiction_id = con.get("contradictionId")
                            if contradiction_id and contradiction_id not in candidate_contradiction_ids:
                                candidate_contradiction_ids.append(contradiction_id)

            # ③ 공개 타임라인 시간대 이벤트
            if entities.time_expressions:
                rows = self._graph_repo.find_timeline_events(
                    case_id=case_id,
                    time_expressions=entities.time_expressions,
                )
                for row in rows:
                    if row.get("title"):
                        timeline_events.append({
                            "id": row["timelineId"],
                            "time": row.get("time"),
                            "title": row["title"],
                            "description": row.get("description", ""),
                        })

            debug["resultCounts"] = {
                "timelineEvents": len(timeline_events),
                "evidence": len(matched_evidence),
                "statements": len(matched_statements),
                "candidateContradictions": len(candidate_contradiction_ids),
            }

        except Exception as exc:
            logger.warning(
                "knowledge_retriever query error",
                extra={"service": "backend", "reason": type(exc).__name__},
            )
            debug["error"] = type(exc).__name__

        matched_statement_ids = [item["id"] for item in matched_statements if item.get("id")]
        matched_evidence_ids = [item["id"] for item in matched_evidence if item.get("id")]
        matched_timeline_ids = [item["id"] for item in timeline_events if item.get("id")]
        note_fact_source_refs = {
            key: value
            for key, value in {
                "statementIds": matched_statement_ids,
                "evidenceIds": matched_evidence_ids,
                "timelineIds": matched_timeline_ids,
                "contradictionIds": candidate_contradiction_ids,
            }.items()
            if value
        }
        return DialogueRetrievedContext(
            character_context=CharacterRetrievedContext(
                matched_timeline_events=timeline_events,
                matched_evidence=matched_evidence,
                matched_statements=matched_statements,
                alibi_summary=alibi_summary,
                fact_boundary=allowed_statement_text,
                retrieval_debug=debug,
            ),
            event_context=GameMasterEventContext(
                matched_statement_ids=matched_statement_ids,
                matched_evidence_ids=matched_evidence_ids,
                matched_timeline_ids=matched_timeline_ids,
                candidate_contradiction_ids=candidate_contradiction_ids,
                note_fact_source_refs=note_fact_source_refs,
                retrieval_debug=debug,
            ),
            retrieval_debug=debug,
        )

    def retrieve(self, **kwargs: object) -> CharacterRetrievedContext:
        """Compatibility wrapper. Prefer retrieve_character_context or retrieve_event_context."""
        return self.retrieve_character_context(**kwargs)  # type: ignore[arg-type]
