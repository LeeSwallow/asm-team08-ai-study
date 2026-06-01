from __future__ import annotations

import logging

import httpx

from app.ai_engine.core.config import settings

logger = logging.getLogger(__name__)


class DeterministicFallbackLLM:
    """외부 프로바이더 미설정 시 사용하는 로컬 결정론적 fallback."""

    provider_name = "deterministic-fallback"

    def complete(self, prompt: str, *, seed_text: str, max_length: int = 220) -> str:
        return deterministic_clip(seed_text, max_length=max_length)


class UpstageAILLM:
    """Upstage Solar API 클라이언트 (OpenAI 호환 엔드포인트)."""

    BASE_URL = "https://api.upstage.ai/v1/chat/completions"
    provider_name = "upstage"

    def complete(self, prompt: str, *, seed_text: str, max_length: int = 220) -> str:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            response = client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {settings.upstage_api_key}"},
                json={
                    "model": settings.upstage_model_name,
                    "temperature": 0.5,
                    "max_tokens": max(80, min(420, max_length * 2)),
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an AI module inside a Korean detective simulation MVP. "
                                "Follow the provided constraints exactly, avoid adding unapproved facts, "
                                "and answer in concise Korean unless the prompt explicitly says otherwise."
                            ),
                        },
                        {"role": "user", "content": f"{prompt.strip()}\n\nAllowed statement to rewrite:\n{seed_text}"},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return deterministic_clip(content, max_length=max_length)


class OpenAILLM:
    """OpenAI chat 클라이언트. Upstage 장애 시 fallback으로 사용."""

    provider_name = "openai"

    def complete(self, prompt: str, *, seed_text: str, max_length: int = 220) -> str:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.model_name,
                    "temperature": 0.5,
                    "max_tokens": max(80, min(420, max_length * 2)),
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an AI module inside a Korean detective simulation MVP. "
                                "Follow the provided constraints exactly, avoid adding unapproved facts, "
                                "and answer in concise Korean unless the prompt explicitly says otherwise."
                            ),
                        },
                        {"role": "user", "content": f"{prompt.strip()}\n\nAllowed statement to rewrite:\n{seed_text}"},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return deterministic_clip(content, max_length=max_length)


class ChainedLLM:
    """primary 실패 시 fallback LLM으로 자동 전환.

    complete() 호출 후 used_fallback_on_last_call / fallback_reason_on_last_call 을
    읽으면 실제로 어떤 프로바이더가 응답했는지 확인할 수 있다.
    CharacterAgent는 이 값을 읽어 fallbackUsed / provider 메타데이터를 정직하게 보고한다.
    """

    def __init__(self, primary: UpstageAILLM | OpenAILLM, fallback: OpenAILLM | DeterministicFallbackLLM) -> None:
        self.primary = primary
        self.fallback = fallback
        self.used_fallback_on_last_call: bool = False
        self.fallback_reason_on_last_call: str | None = None

    def complete(self, prompt: str, *, seed_text: str, max_length: int = 220) -> str:
        try:
            result = self.primary.complete(prompt, seed_text=seed_text, max_length=max_length)
            self.used_fallback_on_last_call = False
            self.fallback_reason_on_last_call = None
            return result
        except Exception as exc:
            self.used_fallback_on_last_call = True
            self.fallback_reason_on_last_call = type(exc).__name__
            logger.warning(
                "primary llm failed, switching to fallback",
                extra={
                    "service": "ai_engine",
                    "primary": type(self.primary).__name__,
                    "fallback": type(self.fallback).__name__,
                    "error": type(exc).__name__,
                },
            )
            return self.fallback.complete(prompt, seed_text=seed_text, max_length=max_length)


def deterministic_clip(text: str, *, max_length: int = 220) -> str:
    normalized = text.strip()
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max(0, max_length - 1)].rstrip() + "…"


def get_llm() -> ChainedLLM | UpstageAILLM | OpenAILLM | DeterministicFallbackLLM:
    provider = settings.llm_provider.lower()
    if provider in {"upstage", "solar"} and settings.upstage_api_key:
        if settings.openai_api_key:
            return ChainedLLM(primary=UpstageAILLM(), fallback=OpenAILLM())
        return UpstageAILLM()
    if provider in {"openai", "gpt"} and settings.openai_api_key:
        return OpenAILLM()
    return DeterministicFallbackLLM()


def llm_status() -> dict[str, str | bool | int | None]:
    provider = settings.llm_provider.lower()
    timeout_ms = int(settings.request_timeout_seconds * 1000)

    if provider in {"upstage", "solar"}:
        if settings.upstage_api_key:
            return {
                "provider": "upstage",
                "requestedProvider": provider,
                "model": settings.upstage_model_name,
                "configured": True,
                "serviceDegraded": False,
                "fallbackConfigured": bool(settings.openai_api_key),
                "fallbackProvider": "openai" if settings.openai_api_key else "deterministic-fallback",
                "timeoutMs": timeout_ms,
            }
        return {
            "provider": "provider-unavailable",
            "requestedProvider": provider,
            "model": settings.upstage_model_name,
            "configured": False,
            "serviceDegraded": True,
            "fallbackConfigured": bool(settings.openai_api_key),
            "degradedReason": "upstage_api_key_missing",
            "timeoutMs": timeout_ms,
        }

    if provider in {"openai", "gpt"}:
        if settings.openai_api_key:
            return {
                "provider": "openai",
                "requestedProvider": provider,
                "model": settings.model_name,
                "configured": True,
                "serviceDegraded": False,
                "fallbackConfigured": False,
                "timeoutMs": timeout_ms,
            }
        return {
            "provider": "provider-unavailable",
            "requestedProvider": provider,
            "model": settings.model_name,
            "configured": False,
            "serviceDegraded": True,
            "fallbackConfigured": False,
            "degradedReason": "openai_api_key_missing",
            "timeoutMs": timeout_ms,
        }

    fallback_configured = provider in {"fallback", "deterministic-fallback", "deterministic"}
    if fallback_configured:
        return {
            "provider": "deterministic-fallback",
            "requestedProvider": provider,
            "model": settings.upstage_model_name,
            "configured": True,
            "serviceDegraded": True,
            "fallbackConfigured": True,
            "degradedReason": "deterministic_fallback_configured",
            "timeoutMs": timeout_ms,
        }
    return {
        "provider": "provider-unavailable",
        "requestedProvider": provider or "unset",
        "model": settings.upstage_model_name,
        "configured": False,
        "serviceDegraded": True,
        "fallbackConfigured": False,
        "degradedReason": "unsupported_provider",
        "timeoutMs": timeout_ms,
    }
