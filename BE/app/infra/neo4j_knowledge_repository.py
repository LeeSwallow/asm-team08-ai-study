from __future__ import annotations

from typing import Any

from app.application.ports import CaseGraphPort, KnowledgeGraphRepositoryPort


class Neo4jKnowledgeGraphRepository(KnowledgeGraphRepositoryPort):
    def __init__(self, graph: CaseGraphPort) -> None:
        self._graph = graph

    @property
    def available(self) -> bool:
        return self._graph.available

    def find_alibi_conflicts(
        self,
        *,
        case_id: str,
        suspect_id: str,
        time_expressions: list[str],
        unlocked_statement_ids: list[str],
        discovered_contradiction_ids: list[str],
    ) -> list[dict[str, Any]]:
        return self._graph.run(
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
            timeExprs=time_expressions,
            unlockedStatementIds=unlocked_statement_ids,
            discoveredContradictionIds=discovered_contradiction_ids,
        )

    def find_evidence_context(
        self,
        *,
        case_id: str,
        evidence_terms: list[str],
        unlocked_evidence_ids: list[str],
    ) -> list[dict[str, Any]]:
        return self._graph.run(
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
            evidenceTerms=[term.lower() for term in evidence_terms],
            unlockedEvidenceIds=unlocked_evidence_ids,
        )

    def find_timeline_events(self, *, case_id: str, time_expressions: list[str]) -> list[dict[str, Any]]:
        return self._graph.run(
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
            timeExprs=time_expressions,
        )
