from __future__ import annotations

import json

from app.ai_engine.core.private_ref_guard import strip_forbidden_private_refs
from app.ai_engine.core.solution_guard import contains_secret
from app.ai_engine.domain.proposed_events import AI_PROPOSABLE_EVENT_TYPES, propose_dialogue_events
from app.ai_engine.schemas.agents import GameMasterAgentInput, GameMasterProposal


FORBIDDEN_GAME_MASTER_EVENT_TYPES = {
    "TENSION_CHANGED",
    "VISUAL_STATE_CHANGED",
    "VISUAL_REACTION_SUGGESTED",
    "PRESSURE_CHANGED",
    "EVIDENCE_UNLOCKED",
    "FINAL_VERDICT_DECIDED",
    "FINAL_VERDICT_SUBMITTED",
    "FINAL_DISCOVERY",
    "FINAL_DISCOVERY_REVEALED",
    "VERDICT_DECIDED",
    "CULPRIT_DISCOVERED",
    "CULPRIT_REVEALED",
    "PRIVATE_TIMELINE_REVEALED",
    "PRIVATE_EVENT_REVEALED",
    "PRIVATE_REVEAL",
    "BE_MUTATION",
    "STATE_MUTATED",
    "SESSION_STATE_MUTATED",
}

PUBLIC_NOTE_EVENT_TYPES = {"NOTE_FACT_ADDED", "NOTE_CONTRADICTION_CANDIDATE_ADDED", "BOOKMARK_SUGGESTED"}


def _contains_forbidden_event_value(value: object) -> bool:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return contains_secret(rendered)[0]


def _checked_reply_allows_events(agent_input: GameMasterAgentInput) -> tuple[bool, str | None]:
    checked = agent_input.checkedReply
    safety = checked.safetyFindings
    if agent_input.providerDegraded or checked.degraded:
        return False, "provider_degraded"
    if checked.blocked or safety.get("blocked", False):
        return False, "checked_reply_blocked"
    if safety.get("leaksSolution", False):
        return False, "checked_reply_leaks_solution"
    if safety.get("violatesCaseFacts", False):
        return False, "checked_reply_violates_case_facts"
    repaired = checked.repaired or safety.get("repaired", False)
    blocked_reason = checked.blockedReason or safety.get("blockedReason")
    if repaired:
        if blocked_reason == "case_fact_scope_repaired":
            return False, "checked_reply_fact_scope_repaired"
        return False, "checked_reply_heavily_repaired"
    return True, None


class GameMasterAgent:
    """Event-proposal-only agent. BE remains authority for validation and mutation."""

    def run(self, agent_input: GameMasterAgentInput) -> GameMasterProposal:
        allowed, reject_reason = _checked_reply_allows_events(agent_input)
        if not allowed:
            return GameMasterProposal(
                proposedEvents=[],
                sourceRefs=agent_input.checkedReply.sourceRefs,
                filteredEventTypes=[],
                rejectedByAgent=[{"type": "*", "reason": reject_reason or "checked_reply_not_safe_for_events"}],
                invariants={
                    "noTensionChanged": True,
                    "noFinalVerdict": True,
                    "noPrivateReveal": True,
                    "noStateMutation": True,
                },
            )
        events = propose_dialogue_events(
            agent_input.payload,
            provider_degraded=agent_input.providerDegraded,
            event_context=agent_input.event_context,
        )
        safe_events = []
        rejected = []
        for event in events:
            if event.type not in AI_PROPOSABLE_EVENT_TYPES or event.type not in PUBLIC_NOTE_EVENT_TYPES:
                rejected.append({"type": event.type, "reason": "not_ai_public_note_or_bookmark_event"})
                continue
            if event.type in FORBIDDEN_GAME_MASTER_EVENT_TYPES:
                rejected.append({"type": event.type, "reason": "state_mutation_or_private_reveal_forbidden"})
                continue
            sanitized_payload = strip_forbidden_private_refs(event.payload)
            sanitized_source_refs = strip_forbidden_private_refs(event.sourceRefs)
            if _contains_forbidden_event_value({"payload": sanitized_payload, "sourceRefs": sanitized_source_refs}):
                rejected.append({"type": event.type, "reason": "private_or_solution_value_forbidden"})
                continue
            safe_events.append(event.model_copy(update={"payload": sanitized_payload, "sourceRefs": sanitized_source_refs}))
        filtered_types = [item["type"] for item in rejected]
        return GameMasterProposal(
            proposedEvents=safe_events,
            sourceRefs=agent_input.checkedReply.sourceRefs,
            filteredEventTypes=filtered_types,
            rejectedByAgent=rejected,
            invariants={
                "noTensionChanged": True,
                "noFinalVerdict": True,
                "noPrivateReveal": True,
                "noStateMutation": True,
            },
        )
