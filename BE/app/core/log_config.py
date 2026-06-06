"""Custom logging configuration for readable agent pipeline logs.

Adds a dedicated handler for the ``app.ai`` logger that prints one concise
line per agent node so that ``docker compose logs -f backend`` shows the
pipeline progression clearly, e.g.::

    [AI] 📥 KnowledgeRetriever  │ 한서연 ← "22:00에 어디 있었나요?"  │ 45ms  │ upstage/solar-pro
    [AI] 🎯 DialogueDirector    │ strategy=answer_public_fact        │ 12ms
    [AI] 🗣️ CharacterAgent      │ upstage/solar-pro                  │ 1,230ms  │ fallback=false
    [AI] ✨ TonePolisher         │ polished=true                      │ 89ms
    [AI] 🛡️ LightRuleCheck      │ safe ✓                             │ 34ms
    [AI] 🎲 GameMaster          │ proposed 2 events                  │ 156ms
"""

from __future__ import annotations

import logging

# ---------- public names ----------

AI_LOGGER_NAME = "app.ai"

# ---------- node → emoji/label map ----------

_NODE_DISPLAY: dict[str, tuple[str, str]] = {
    "load_context": ("📥", "LoadContext"),
    "validate_scope": ("✅", "ValidateScope"),
    "KnowledgeRetriever": ("📥", "KnowledgeRetriever"),
    "DialogueDirectorAgent": ("🎯", "DialogueDirector"),
    "CharacterAgent": ("🗣️", "CharacterAgent"),
    "DialogueTonePolisher": ("✨", "TonePolisher"),
    "LightRuleCheck": ("🛡️", "LightRuleCheck"),
    "GroundingCheckAgent": ("🔍", "GroundingCheck"),
    "GameMasterAgent": ("🎲", "GameMaster"),
    "format_response": ("📤", "FormatResponse"),
}


class _AgentLogFormatter(logging.Formatter):
    """One-line formatter that uses *extra* fields from ``emit_ai_node_log``."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        # Fallback for non-agent log messages on this logger.
        if not getattr(record, "node", None):
            return super().format(record)

        emoji, label = _NODE_DISPLAY.get(record.node, ("⚙️", record.node))  # type: ignore[attr-defined]

        parts: list[str] = [f"[AI] {emoji} {label:<22s}│"]

        # Suspect + question preview
        suspect = getattr(record, "suspect_name", None)
        question = getattr(record, "question_preview", None)
        if suspect or question:
            bits: list[str] = []
            if suspect:
                bits.append(f"{suspect}")
            if question:
                q = str(question)[:50]
                bits.append(f"← \"{q}\"")
            parts.append(" ".join(bits) + "  │")

        # Latency
        latency = getattr(record, "latency_ms", None)
        if latency is not None:
            parts.append(f"{int(latency):>5,}ms  │")

        # Provider / model
        provider = getattr(record, "provider", None)
        model = getattr(record, "model", None)
        if provider:
            p = f"{provider}" + (f"/{model}" if model else "")
            parts.append(f"{p}  │")

        # Status flags
        flags: list[str] = []
        if getattr(record, "fallback_used", False):
            flags.append("fallback=⚠️")
        if getattr(record, "repaired", False):
            flags.append("repaired=🔧")
        reason = getattr(record, "blocked_reason", None)
        if reason:
            flags.append(f"blocked={reason}")

        # Special per-node extras
        if record.node == "DialogueDirectorAgent" and reason:
            flags.append(f"strategy={reason}")
        if record.node == "GameMasterAgent":
            count = getattr(record, "proposed_event_count", 0)
            flags.append(f"proposed {count} event{'s' if count != 1 else ''}")
        if record.node == "LightRuleCheck" and not reason:
            flags.append("safe ✓")
        if record.node == "DialogueTonePolisher":
            flags.append("polished=true" if getattr(record, "repaired", False) else "polished=false")

        if flags:
            parts.append("  ".join(flags))

        return " ".join(parts)


def setup_agent_logging() -> None:
    """Install the agent-friendly console handler.

    Safe to call multiple times – duplicate handlers are prevented.
    """
    ai_logger = logging.getLogger(AI_LOGGER_NAME)
    ai_logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on repeated calls.
    if any(getattr(h, "_is_agent_handler", False) for h in ai_logger.handlers):
        return

    handler = logging.StreamHandler()
    handler.setFormatter(_AgentLogFormatter())
    handler._is_agent_handler = True  # type: ignore[attr-defined]
    ai_logger.addHandler(handler)

    # Prevent propagation to root so we don't get double-printed lines.
    ai_logger.propagate = False
