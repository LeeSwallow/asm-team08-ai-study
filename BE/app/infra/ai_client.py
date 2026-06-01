from typing import Any, Dict, Optional

import logging
import httpx

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self, base_url: Optional[str], timeout_seconds: float = 2.0, max_retries: int = 1):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)

    async def dialogue_response_info(self, payload: Dict[str, Any], fallback: str) -> Dict[str, Any]:
        result = await self._post("/internal/v1/dialogue/respond", payload)
        if self._is_degraded(result):
            return self._degraded_result(result)
        answer = result.get("answer") or result.get("text") or fallback
        proposed_events = result.get("proposedEvents") or []
        if not isinstance(proposed_events, list):
            proposed_events = []
        return {
            "answer": answer,
            "proposedEvents": proposed_events,
            "fallbackUsed": False,
            "degraded": False,
            "provider": result.get("provider") or "ai-service",
            "model": result.get("model"),
            "intent": result.get("intent"),
            "dialogueMode": result.get("dialogueMode"),
            "safety": result.get("safety") or {"status": "checked"},
        }

    async def dialogue_response(self, payload: Dict[str, Any], fallback: str) -> str:
        return (await self.dialogue_response_info(payload, fallback))["answer"]

    async def notes_summary(self, payload: Dict[str, Any], fallback: str) -> str:
        result = await self._post("/internal/v1/notes/summary", payload)
        if self._is_degraded(result):
            logger.warning(
                "ai notes summary degraded",
                extra={"service": "backend", "route": "/internal/v1/notes/summary", "fallback_used": False},
            )
            return "AI 요약 서비스를 사용할 수 없습니다. 잠시 후 다시 시도하세요."
        return result.get("summary") or fallback

    async def hint(self, payload: Dict[str, Any], fallback: str) -> str:
        result = await self._post("/internal/v1/hints", payload)
        if self._is_degraded(result):
            logger.warning(
                "ai hint degraded",
                extra={"service": "backend", "route": "/internal/v1/hints", "fallback_used": False},
            )
            return "AI 힌트 서비스를 사용할 수 없습니다. 잠시 후 다시 시도하세요."
        return result.get("hint") or result.get("text") or fallback

    async def ending(self, payload: Dict[str, Any], fallback: str) -> str:
        result = await self._post("/internal/v1/endings/explain", payload)
        if self._is_degraded(result):
            logger.warning(
                "ai ending degraded",
                extra={"service": "backend", "route": "/internal/v1/endings/explain", "fallback_used": False},
            )
            return "AI 엔딩 해설 서비스를 사용할 수 없습니다. 판정 결과만 표시합니다."
        return result.get("ending") or result.get("text") or fallback

    async def health(self) -> Dict[str, Any]:
        result = await self._get("/health")
        if self._is_degraded(result) or result.get("configured") is False:
            return {"ok": False, **result}
        return {"ok": True, **result}

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.base_url:
            return self._degraded_payload(path, "ai_service_not_configured")
        last_error = "unknown"
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(f"{self.base_url}{path}", json=payload)
                    if response.status_code >= 500 and attempt < self.max_retries:
                        last_error = f"http_{response.status_code}"
                        continue
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, dict):
                        return data
                    return self._degraded_payload(path, "invalid_json_shape")
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError, httpx.HTTPError) as exc:
                last_error = type(exc).__name__
                if attempt < self.max_retries:
                    continue
                return self._degraded_payload(path, last_error)
        return self._degraded_payload(path, last_error)

    async def _get(self, path: str) -> Dict[str, Any]:
        if not self.base_url:
            return self._degraded_payload(path, "ai_service_not_configured")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}{path}")
                response.raise_for_status()
                data = response.json()
                return data if isinstance(data, dict) else {}
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError, httpx.HTTPError) as exc:
            return self._degraded_payload(path, type(exc).__name__)

    def _degraded_payload(self, path: str, reason: str) -> Dict[str, Any]:
        logger.warning(
            "ai service degraded",
            extra={"service": "backend", "route": path, "fallback_used": False, "reason": reason},
        )
        return {
            "_degraded": True,
            "reason": reason,
            "provider": "ai-service",
            "safety": {"status": "degraded", "blockedReason": reason, "fallbackUsed": False},
        }

    def _degraded_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "answer": None,
            "proposedEvents": [],
            "fallbackUsed": False,
            "degraded": True,
            "degradedReason": result.get("reason") or "ai_service_unavailable",
            "provider": result.get("provider") or "ai-service",
            "model": None,
            "intent": None,
            "dialogueMode": None,
            "safety": result.get("safety") or {"status": "degraded"},
        }

    def _is_degraded(self, result: Dict[str, Any]) -> bool:
        return bool(
            result.get("_degraded")
            or result.get("degraded")
            or result.get("serviceDegraded")
            or result.get("fallbackUsed") is True
        )
