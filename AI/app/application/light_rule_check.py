from __future__ import annotations

from app.core.guard import guard_dialogue_text
from app.schemas.agents import CheckedCharacterReply, LightRuleCheckInput


class LightRuleCheck:
    """Safety-only guard. It repairs or blocks text, but never mutates game state."""

    def run(self, agent_input: LightRuleCheckInput) -> CheckedCharacterReply:
        final_text, safety = guard_dialogue_text(
            agent_input.draft.draftText,
            agent_input.allowedStatement.text,
            reveal_allowed=agent_input.revealAllowed,
            enforce_statement_scope=agent_input.enforceStatementScope,
            allowed_context_terms=tuple(agent_input.allowedContextTerms),
        )
        repaired_text = final_text if safety.repaired else None
        blocked_text = agent_input.draft.draftText if safety.blocked_reason else None
        blocked = bool(safety.leaks_solution or safety.violates_case_facts)
        blocked_reason = safety.blocked_reason
        return CheckedCharacterReply(
            requestId=agent_input.requestId or agent_input.draft.requestId,
            correlationId=agent_input.correlationId or agent_input.draft.correlationId,
            suspectId=agent_input.draft.suspectId,
            finalText=final_text,
            repairedText=repaired_text,
            blockedText=blocked_text,
            repaired=safety.repaired,
            blocked=blocked,
            blockedReason=blocked_reason,
            usedRefs=agent_input.draft.usedRefs,
            sourceRefs=agent_input.draft.sourceRefs,
            personaOverlayId=agent_input.draft.personaOverlayId,
            safetyFindings={
                "leaksSolution": safety.leaks_solution,
                "violatesCaseFacts": safety.violates_case_facts,
                "blockedTerms": list(safety.blocked_terms),
                "repaired": safety.repaired,
                "blocked": blocked,
                "blockedReason": blocked_reason,
            },
            fallbackUsed=agent_input.draft.fallbackUsed,
            degraded=agent_input.draft.degraded,
            provider=agent_input.draft.provider,
            model=agent_input.draft.model,
            errorType=agent_input.draft.errorType,
        )
