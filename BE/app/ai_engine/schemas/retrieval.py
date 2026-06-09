from __future__ import annotations

from dataclasses import dataclass, field


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
