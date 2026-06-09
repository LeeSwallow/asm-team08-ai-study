from __future__ import annotations

import logging

from app.ai_engine.retrieval.context_queries import (
    retrieve_evidence_context,
    retrieve_statement_context,
    retrieve_timeline_context,
)
from app.ai_engine.retrieval.question_entity_extractor import extract_question_entities
from app.ai_engine.schemas.retrieval import (
    CharacterRetrievedContext,
    DialogueRetrievedContext,
    GameMasterEventContext,
    QuestionEntities,
    RetrievedContext,
)
from app.application.ports import KnowledgeGraphRepositoryPort

logger = logging.getLogger(__name__)


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

        assert self._graph_repo is not None
        entities = extract_question_entities(question_text, allowed_statement_text)
        debug = self._base_debug(entities)

        timeline_events: list[dict] = []
        matched_evidence: list[dict] = []
        matched_statements: list[dict] = []
        candidate_contradiction_ids: list[str] = []
        alibi_summary: str | None = None

        try:
            matched_statements, candidate_contradiction_ids, alibi_summary = retrieve_statement_context(
                self._graph_repo,
                case_id=case_id,
                suspect_id=suspect_id,
                entities=entities,
                unlocked_statement_ids=unlocked_statement_ids,
                discovered_contradiction_ids=discovered_contradiction_ids,
            )
            matched_evidence, candidate_contradiction_ids = retrieve_evidence_context(
                self._graph_repo,
                case_id=case_id,
                entities=entities,
                unlocked_evidence_ids=unlocked_evidence_ids,
                candidate_contradiction_ids=candidate_contradiction_ids,
            )
            timeline_events = retrieve_timeline_context(self._graph_repo, case_id=case_id, entities=entities)
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

        return build_dialogue_retrieved_context(
            allowed_statement_text=allowed_statement_text,
            timeline_events=timeline_events,
            matched_evidence=matched_evidence,
            matched_statements=matched_statements,
            candidate_contradiction_ids=candidate_contradiction_ids,
            alibi_summary=alibi_summary,
            debug=debug,
        )

    @staticmethod
    def _base_debug(entities: QuestionEntities) -> dict:
        return {
            "entities": {
                "timeExpressions": entities.time_expressions,
                "locationTerms": entities.location_terms,
                "evidenceTerms": entities.evidence_terms,
            },
            "neo4j": True,
        }

    def retrieve(self, **kwargs: object) -> CharacterRetrievedContext:
        """Compatibility wrapper. Prefer retrieve_character_context or retrieve_event_context."""
        return self.retrieve_character_context(**kwargs)  # type: ignore[arg-type]


def build_dialogue_retrieved_context(
    *,
    allowed_statement_text: str,
    timeline_events: list[dict],
    matched_evidence: list[dict],
    matched_statements: list[dict],
    candidate_contradiction_ids: list[str],
    alibi_summary: str | None,
    debug: dict,
) -> DialogueRetrievedContext:
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
