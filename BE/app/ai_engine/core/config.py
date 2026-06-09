from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field, ValidationError
import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yml"
CONFIG_PATH_ENV = "AI_ENGINE_CONFIG_PATH"


class LLMGenerationConfig(BaseModel):
    temperature: float = 0.35
    min_tokens: int = 80
    max_tokens: int = 420
    max_tokens_multiplier: int = 2


class UpstageConfig(BaseModel):
    api_url: str = "https://api.upstage.ai/v1/chat/completions"
    model_name: str = "solar-pro"


class OpenAIConfig(BaseModel):
    api_url: str = "https://api.openai.com/v1/chat/completions"
    model_name: str = "gpt-4o-mini"
    tone_model_name: str | None = None


class LLMConfig(BaseModel):
    provider: str = "fallback"
    request_timeout_seconds: float = 8.0
    generation: LLMGenerationConfig = Field(default_factory=LLMGenerationConfig)
    upstage: UpstageConfig = Field(default_factory=UpstageConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)


class LightRuleCheckConfig(BaseModel):
    max_regen_attempts: int = 2


class AgentConfig(BaseModel):
    light_rule_check: LightRuleCheckConfig = Field(default_factory=LightRuleCheckConfig)


class AIEngineConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agents: AgentConfig = Field(default_factory=AgentConfig)


class Settings(BaseModel):
    config_path: Path
    config: AIEngineConfig

    # Flat compatibility properties for current call sites.
    llm_provider: str
    upstage_api_key: str | None
    upstage_api_url: str
    upstage_model_name: str
    openai_api_key: str | None
    openai_api_url: str
    model_name: str
    tone_model_name: str
    request_timeout_seconds: float
    generation_temperature: float
    generation_min_tokens: int
    generation_max_tokens: int
    generation_max_tokens_multiplier: int
    light_rule_check_max_regen_attempts: int


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"AI engine config must be a YAML mapping: {path}")
    return dict(raw)


def _env_str(name: str, fallback: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return fallback
    return value


def _env_optional(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _env_float(name: str, fallback: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return fallback
    return float(value)


def _env_int(name: str, fallback: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return fallback
    return int(value)


def _build_settings(config_path: Path) -> Settings:
    defaults = AIEngineConfig().model_dump()
    yaml_config = _deep_merge(defaults, _load_yaml_config(config_path))
    try:
        config = AIEngineConfig.model_validate(yaml_config)
    except ValidationError as exc:
        raise ValueError(f"Invalid AI engine config file: {config_path}\n{exc}") from exc

    openai_tone_model = config.llm.openai.tone_model_name or config.llm.openai.model_name

    return Settings(
        config_path=config_path,
        config=config,
        llm_provider=_env_str("AI_LLM_PROVIDER", config.llm.provider),
        upstage_api_key=_env_optional("AI_UPSTAGE_API_KEY", "UPSTAGE_API_KEY"),
        upstage_api_url=_env_str("AI_UPSTAGE_API_URL", config.llm.upstage.api_url),
        upstage_model_name=_env_str("AI_UPSTAGE_MODEL_NAME", config.llm.upstage.model_name),
        openai_api_key=_env_optional("AI_OPENAI_API_KEY", "OPENAI_API_KEY"),
        openai_api_url=_env_str("AI_OPENAI_API_URL", config.llm.openai.api_url),
        model_name=_env_str("AI_MODEL_NAME", config.llm.openai.model_name),
        tone_model_name=_env_str("AI_TONE_MODEL_NAME", _env_str("AI_MODEL_NAME", openai_tone_model)),
        request_timeout_seconds=_env_float("AI_REQUEST_TIMEOUT_SECONDS", config.llm.request_timeout_seconds),
        generation_temperature=_env_float("AI_GENERATION_TEMPERATURE", config.llm.generation.temperature),
        generation_min_tokens=_env_int("AI_GENERATION_MIN_TOKENS", config.llm.generation.min_tokens),
        generation_max_tokens=_env_int("AI_GENERATION_MAX_TOKENS", config.llm.generation.max_tokens),
        generation_max_tokens_multiplier=_env_int(
            "AI_GENERATION_MAX_TOKENS_MULTIPLIER", config.llm.generation.max_tokens_multiplier
        ),
        light_rule_check_max_regen_attempts=_env_int(
            "AI_LIGHT_RULE_CHECK_MAX_REGEN_ATTEMPTS", config.agents.light_rule_check.max_regen_attempts
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = Path(os.getenv(CONFIG_PATH_ENV, str(DEFAULT_CONFIG_PATH))).expanduser().resolve()
    return _build_settings(config_path)


settings = get_settings()
