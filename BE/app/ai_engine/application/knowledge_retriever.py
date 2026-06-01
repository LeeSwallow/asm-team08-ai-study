from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

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
class RetrievedContext:
    matched_timeline_events: list[dict] = field(default_factory=list)
    matched_evidence: list[dict] = field(default_factory=list)
    matched_statements: list[dict] = field(default_factory=list)
    related_contradictions: list[dict] = field(default_factory=list)
    alibi_summary: str | None = None
    fact_boundary: str = ""
    retrieval_debug: dict = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not (
            self.matched_timeline_events
            or self.matched_evidence
            or self.matched_statements
            or self.related_contradictions
        )


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

    def __init__(self, case_graph: Any | None = None) -> None:  # noqa: ANN401
        self._graph = case_graph

    @property
    def _available(self) -> bool:
        return self._graph is not None and getattr(self._graph, "available", False)

    def retrieve(
        self,
        *,
        case_id: str,
        suspect_id: str,
        question_text: str,
        allowed_statement_text: str,
        unlocked_statement_ids: list[str],
        unlocked_evidence_ids: list[str],
        discovered_contradiction_ids: list[str],
    ) -> RetrievedContext:
        if not self._available:
            return RetrievedContext(fact_boundary=allowed_statement_text)

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
        related_contradictions: list[dict] = []
        alibi_summary: str | None = None

        try:
            # ① 용의자 + 시간대 → 알리바이 진술 + 충돌 증거
            if entities.time_expressions or suspect_id:
                rows = self._graph.run(
                    """
                    MATCH (ch:Character {caseId: $caseId, characterId: $suspectId})
                          -[:MADE_STATEMENT]->(s:Statement)
                    WHERE (size($timeExprs) = 0 OR s.timeWindow IN $timeExprs)
                      AND (s.statementId IN $unlockedStatementIds OR s.initiallyVisible = true)
                    OPTIONAL MATCH (con:Contradiction)-[:REQUIRES_STATEMENT]->(s)
                    OPTIONAL MATCH (con)-[:REQUIRES_EVIDENCE]->(e:Evidence)
                    WHERE NOT con.contradictionId IN $discoveredContradictionIds
                    RETURN s.statementId AS statementId,
                           s.text AS statementText,
                           s.timeWindow AS timeWindow,
                           s.location AS location,
                           collect(DISTINCT {
                               contradictionId: con.contradictionId,
                               title: con.title,
                               severity: con.severity
                           }) AS contradictions,
                           collect(DISTINCT {
                               evidenceId: e.evidenceId,
                               name: e.name
                           }) AS evidenceConflicts
                    """,
                    caseId=case_id,
                    suspectId=suspect_id,
                    timeExprs=entities.time_expressions,
                    unlockedStatementIds=unlocked_statement_ids,
                    discoveredContradictionIds=discovered_contradiction_ids,
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
                            if con.get("contradictionId") and con not in related_contradictions:
                                related_contradictions.append(con)

            # ② 질문에 언급된 증거 → 관련 모순 탐색
            if entities.evidence_terms and unlocked_evidence_ids:
                rows = self._graph.run(
                    """
                    MATCH (e:Evidence {caseId: $caseId})
                    WHERE any(term IN $evidenceTerms
                              WHERE toLower(e.name) CONTAINS term
                                 OR toLower(e.description) CONTAINS term)
                      AND (e.evidenceId IN $unlockedEvidenceIds OR e.initiallyVisible = true)
                    OPTIONAL MATCH (con:Contradiction)-[:REQUIRES_EVIDENCE]->(e)
                    OPTIONAL MATCH (con)-[:REQUIRES_STATEMENT]->(s:Statement)
                    RETURN e.evidenceId AS evidenceId,
                           e.name AS name,
                           e.description AS description,
                           e.timeWindow AS timeWindow,
                           collect(DISTINCT {
                               contradictionId: con.contradictionId,
                               title: con.title,
                               severity: con.severity
                           }) AS contradictions,
                           collect(DISTINCT {
                               statementId: s.statementId,
                               text: s.text
                           }) AS relatedStatements
                    """,
                    caseId=case_id,
                    evidenceTerms=[t.lower() for t in entities.evidence_terms],
                    unlockedEvidenceIds=unlocked_evidence_ids,
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
                            if con.get("contradictionId") and con not in related_contradictions:
                                related_contradictions.append(con)

            # ③ 공개 타임라인 시간대 이벤트
            if entities.time_expressions:
                rows = self._graph.run(
                    """
                    MATCH (t:TimelineEvent {caseId: $caseId})
                    WHERE t.hidden = false
                      AND (size($timeExprs) = 0 OR t.time IN $timeExprs)
                    RETURN t.timelineId AS timelineId,
                           t.time AS time,
                           t.title AS title,
                           t.description AS description
                    ORDER BY t.time
                    LIMIT 6
                    """,
                    caseId=case_id,
                    timeExprs=entities.time_expressions,
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
                "contradictions": len(related_contradictions),
            }

        except Exception as exc:
            logger.warning(
                "knowledge_retriever query error",
                extra={"service": "backend", "reason": type(exc).__name__},
            )
            debug["error"] = type(exc).__name__

        return RetrievedContext(
            matched_timeline_events=timeline_events,
            matched_evidence=matched_evidence,
            matched_statements=matched_statements,
            related_contradictions=[c for c in related_contradictions if c.get("contradictionId")],
            alibi_summary=alibi_summary,
            fact_boundary=allowed_statement_text,
            retrieval_debug=debug,
        )


# ── 글로벌 인스턴스 관리 ─────────────────────────────────────────────────────

_retriever: KnowledgeRetriever | None = None


def get_knowledge_retriever() -> KnowledgeRetriever:
    global _retriever
    if _retriever is None:
        from app.core.config import get_settings  # lazy import to avoid circular
        settings = get_settings()
        if settings.neo4j_uri:
            try:
                from app.infra.case_graph import CaseGraph
                graph = CaseGraph(
                    uri=settings.neo4j_uri,
                    user=settings.neo4j_user,
                    password=settings.neo4j_password,
                )
                _retriever = KnowledgeRetriever(graph)
                logger.info("knowledge_retriever initialized with Neo4j")
            except Exception as exc:
                logger.warning(
                    "knowledge_retriever neo4j init failed, using no-op retriever",
                    extra={"service": "backend", "reason": type(exc).__name__},
                )
                _retriever = KnowledgeRetriever(None)
        else:
            logger.info("BE_NEO4J_URI not set — knowledge_retriever in no-op mode")
            _retriever = KnowledgeRetriever(None)
    return _retriever


# type alias for annotations
from typing import Any  # noqa: E402
