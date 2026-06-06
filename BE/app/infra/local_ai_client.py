import asyncio
import logging
from typing import Any, Dict

from app.ai_engine.core.llm import llm_status
from app.ai_engine.graph.dialogue_graph import run_dialogue_graph
from app.ai_engine.graph.ending_graph import run_ending_graph
from app.ai_engine.graph.hint_graph import run_hint_graph
from app.ai_engine.graph.summary_graph import run_summary_graph
from app.ai_engine.schemas.dialogue import DialogueRequest
from app.ai_engine.schemas.endings import EndingExplainRequest
from app.ai_engine.schemas.hints import HintRequest
from app.ai_engine.schemas.notes import NotesSummaryRequest
from app.infra.knowledge_retriever_provider import get_knowledge_retriever

logger = logging.getLogger(__name__)


def _public_runtime_diagnostics(diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    director = (diagnostics or {}).get("dialogueDirector")
    if isinstance(director, dict):
        result["dialogueDirector"] = {
            "strategy": director.get("strategy"),
            "seedText": director.get("seedText"),
            "allowedAdmissionLevel": director.get("allowedAdmissionLevel"),
            "focusTerms": list(director.get("focusTerms") or []),
            "reason": director.get("reason"),
        }
    grounding = (diagnostics or {}).get("grounding")
    if isinstance(grounding, dict):
        result["grounding"] = {
            "checked": bool(grounding.get("checked", False)),
            "repaired": bool(grounding.get("repaired", False)),
            "basis": grounding.get("basis"),
            "repairReason": grounding.get("repairReason"),
            "finalTextSource": grounding.get("finalTextSource"),
            "issues": list(grounding.get("issues") or []),
            "missingAnchorFacts": list(grounding.get("missingAnchorFacts") or []),
            "unsupportedFacts": list(grounding.get("unsupportedFacts") or []),
            "anchorCoverage": grounding.get("anchorCoverage"),
        }
    return result


class LocalAIClient:
    async def dialogue_response_info(self, payload: Dict[str, Any], fallback: str) -> Dict[str, Any]:
        try:
            req = DialogueRequest.model_validate(payload)
            result = await asyncio.to_thread(run_dialogue_graph, req, get_knowledge_retriever())
            answer = result.text or fallback
            proposed_events = [e.model_dump(mode="json") for e in result.proposedEvents]
            safety = result.safety.model_dump(mode="json") if result.safety else {"status": "checked"}
            safety.setdefault("status", "degraded" if result.degraded else "checked")
            return {
                "answer": answer,
                "proposedEvents": proposed_events,
                "fallbackUsed": result.fallbackUsed,
                "degraded": result.degraded,
                "degradedReason": None,
                "provider": result.provider or "local",
                "model": result.model,
                "intent": result.intent,
                "dialogueMode": result.dialogueMode,
                "safety": safety,
                "runtimeDiagnostics": _public_runtime_diagnostics(result.runtimeDiagnostics),
            }
        except Exception as exc:
            reason = type(exc).__name__
            logger.warning(
                "local ai dialogue_response_info failed",
                extra={"service": "backend", "reason": reason, "fallback_used": False},
            )
            return {
                "answer": None,
                "proposedEvents": [],
                "fallbackUsed": False,
                "degraded": True,
                "degradedReason": reason,
                "provider": "local",
                "model": None,
                "intent": None,
                "dialogueMode": None,
                "safety": {"status": "degraded", "fallbackUsed": False, "degraded": True},
            }

    async def dialogue_response(self, payload: Dict[str, Any], fallback: str) -> str:
        return (await self.dialogue_response_info(payload, fallback))["answer"]

    async def notes_summary(self, payload: Dict[str, Any], fallback: str) -> str:
        try:
            req = NotesSummaryRequest.model_validate(payload)
            result = await asyncio.to_thread(run_summary_graph, req)
            return result.summary or fallback
        except Exception as exc:
            logger.warning("local ai notes_summary failed", extra={"reason": str(exc)})
            return fallback

    async def hint(self, payload: Dict[str, Any], fallback: str) -> str:
        try:
            req = HintRequest.model_validate(payload)
            result = await asyncio.to_thread(run_hint_graph, req)
            return result.text or fallback
        except Exception as exc:
            logger.warning("local ai hint failed", extra={"reason": str(exc)})
            return fallback

    async def ending(self, payload: Dict[str, Any], fallback: str) -> str:
        try:
            req = EndingExplainRequest.model_validate(payload)
            result = await asyncio.to_thread(run_ending_graph, req)
            return result.explanation or fallback
        except Exception as exc:
            logger.warning("local ai ending failed", extra={"reason": str(exc)})
            return fallback

    async def health(self) -> Dict[str, Any]:
        status = llm_status()
        ok = not status.get("serviceDegraded", True)
        return {"ok": ok, **status}
