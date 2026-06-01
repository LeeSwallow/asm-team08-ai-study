from __future__ import annotations

import httpx

from app.core.config import settings


class DeterministicFallbackLLM:
    """Explicit local fallback renderer used when no external provider is configured."""

    def complete(self, prompt: str, *, seed_text: str, max_length: int = 220) -> str:
        return deterministic_clip(seed_text, max_length=max_length)


class OpenAILLM:
    """Minimal synchronous OpenAI chat client. Fallback is handled by application orchestration."""

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


def deterministic_clip(text: str, *, max_length: int = 220) -> str:
    normalized = text.strip()
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max(0, max_length - 1)].rstrip() + "…"


def get_llm() -> OpenAILLM | DeterministicFallbackLLM:
    if settings.llm_provider.lower() in {"openai", "gpt"} and settings.openai_api_key:
        return OpenAILLM()
    return DeterministicFallbackLLM()


def llm_status() -> dict[str, str | bool]:
    requested_provider = settings.llm_provider.lower()
    fallback_configured = requested_provider in {"fallback", "deterministic-fallback", "deterministic"}
    if requested_provider in {"openai", "gpt"}:
        configured = bool(settings.openai_api_key)
        if configured:
            return {
                "provider": "openai",
                "requestedProvider": requested_provider,
                "model": settings.model_name,
                "configured": True,
                "serviceDegraded": False,
                "fallbackConfigured": False,
                "timeoutMs": int(settings.request_timeout_seconds * 1000),
            }
        return {
            "provider": "provider-unavailable",
            "requestedProvider": requested_provider,
            "model": settings.model_name,
            "configured": False,
            "serviceDegraded": True,
            "fallbackConfigured": fallback_configured,
            "degradedReason": "openai_api_key_missing",
            "timeoutMs": int(settings.request_timeout_seconds * 1000),
        }
    if fallback_configured:
        return {
            "provider": "deterministic-fallback",
            "requestedProvider": requested_provider,
            "model": settings.model_name,
            "configured": True,
            "serviceDegraded": True,
            "fallbackConfigured": True,
            "degradedReason": "deterministic_fallback_configured",
            "timeoutMs": int(settings.request_timeout_seconds * 1000),
        }
    return {
        "provider": "provider-unavailable",
        "requestedProvider": requested_provider or "unset",
        "model": settings.model_name,
        "configured": False,
        "serviceDegraded": True,
        "fallbackConfigured": False,
        "degradedReason": "unsupported_provider",
        "timeoutMs": int(settings.request_timeout_seconds * 1000),
    }
