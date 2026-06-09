from __future__ import annotations

from app.ai_engine.schemas.retrieval import QuestionEntities
from app.application.ports import KnowledgeGraphRepositoryPort


def retrieve_statement_context(
    graph_repo: KnowledgeGraphRepositoryPort,
    *,
    case_id: str,
    suspect_id: str,
    entities: QuestionEntities,
    unlocked_statement_ids: list[str],
    discovered_contradiction_ids: list[str],
) -> tuple[list[dict], list[str], str | None]:
    matched_statements: list[dict] = []
    candidate_contradiction_ids: list[str] = []
    alibi_summary: str | None = None
    if not (entities.time_expressions or suspect_id):
        return matched_statements, candidate_contradiction_ids, alibi_summary

    rows = graph_repo.find_alibi_conflicts(
        case_id=case_id,
        suspect_id=suspect_id,
        time_expressions=entities.time_expressions,
        unlocked_statement_ids=unlocked_statement_ids,
        discovered_contradiction_ids=discovered_contradiction_ids,
    )
    for row in rows:
        if not row.get("statementText"):
            continue
        matched_statements.append({
            "id": row["statementId"],
            "text": row["statementText"],
            "timeWindow": row.get("timeWindow"),
            "location": row.get("location"),
        })
        if alibi_summary is None and row.get("timeWindow"):
            alibi_summary = f"{row['timeWindow']} {row.get('location', '')} (공개 알리바이)".strip()
        append_contradiction_ids(candidate_contradiction_ids, row.get("contradictions") or [])
    return matched_statements, candidate_contradiction_ids, alibi_summary


def retrieve_evidence_context(
    graph_repo: KnowledgeGraphRepositoryPort,
    *,
    case_id: str,
    entities: QuestionEntities,
    unlocked_evidence_ids: list[str],
    candidate_contradiction_ids: list[str],
) -> tuple[list[dict], list[str]]:
    matched_evidence: list[dict] = []
    if not (entities.evidence_terms and unlocked_evidence_ids):
        return matched_evidence, candidate_contradiction_ids

    rows = graph_repo.find_evidence_context(
        case_id=case_id,
        evidence_terms=entities.evidence_terms,
        unlocked_evidence_ids=unlocked_evidence_ids,
    )
    for row in rows:
        if not row.get("name"):
            continue
        matched_evidence.append({
            "id": row["evidenceId"],
            "name": row["name"],
            "description": row.get("description", ""),
            "timeWindow": row.get("timeWindow"),
        })
        append_contradiction_ids(candidate_contradiction_ids, row.get("contradictions") or [])
    return matched_evidence, candidate_contradiction_ids


def retrieve_timeline_context(graph_repo: KnowledgeGraphRepositoryPort, *, case_id: str, entities: QuestionEntities) -> list[dict]:
    if not entities.time_expressions:
        return []
    rows = graph_repo.find_timeline_events(case_id=case_id, time_expressions=entities.time_expressions)
    return [
        {
            "id": row["timelineId"],
            "time": row.get("time"),
            "title": row["title"],
            "description": row.get("description", ""),
        }
        for row in rows
        if row.get("title")
    ]


def append_contradiction_ids(target: list[str], contradictions: list[dict]) -> None:
    for contradiction in contradictions:
        contradiction_id = contradiction.get("contradictionId")
        if contradiction_id and contradiction_id not in target:
            target.append(contradiction_id)
