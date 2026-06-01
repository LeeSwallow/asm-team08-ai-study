from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    llm_provider: str = os.getenv("AI_LLM_PROVIDER", "fallback")
    openai_api_key: str | None = os.getenv("AI_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    model_name: str = os.getenv("AI_MODEL_NAME", "gpt-4o-mini")
    request_timeout_seconds: float = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "8.0"))


settings = Settings()
