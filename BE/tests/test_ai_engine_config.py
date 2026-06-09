from app.ai_engine.core.config import _build_settings


def test_ai_engine_settings_load_non_secret_values_from_yaml(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("AI_UPSTAGE_MODEL_NAME", raising=False)
    monkeypatch.delenv("AI_GENERATION_TEMPERATURE", raising=False)
    monkeypatch.delenv("AI_LIGHT_RULE_CHECK_MAX_REGEN_ATTEMPTS", raising=False)

    config_path = tmp_path / "ai_engine.yml"
    config_path.write_text(
        """
llm:
  provider: upstage
  request_timeout_seconds: 3.5
  generation:
    temperature: 0.2
    min_tokens: 50
    max_tokens: 300
    max_tokens_multiplier: 3
  upstage:
    api_url: https://example.test/upstage
    model_name: solar-test
  openai:
    api_url: https://example.test/openai
    model_name: gpt-test
    tone_model_name: tone-test
agents:
  light_rule_check:
    max_regen_attempts: 5
""".strip(),
        encoding="utf-8",
    )

    settings = _build_settings(config_path)

    assert settings.llm_provider == "upstage"
    assert settings.request_timeout_seconds == 3.5
    assert settings.generation_temperature == 0.2
    assert settings.generation_min_tokens == 50
    assert settings.generation_max_tokens == 300
    assert settings.generation_max_tokens_multiplier == 3
    assert settings.upstage_api_url == "https://example.test/upstage"
    assert settings.upstage_model_name == "solar-test"
    assert settings.openai_api_url == "https://example.test/openai"
    assert settings.model_name == "gpt-test"
    assert settings.tone_model_name == "tone-test"
    assert settings.light_rule_check_max_regen_attempts == 5
    assert settings.upstage_api_key is None
    assert settings.openai_api_key is None


def test_ai_engine_env_overrides_yaml_but_keys_remain_env_only(tmp_path, monkeypatch):
    config_path = tmp_path / "ai_engine.yml"
    config_path.write_text(
        """
llm:
  provider: fallback
  upstage:
    model_name: yaml-solar
  openai:
    model_name: yaml-gpt
agents:
  light_rule_check:
    max_regen_attempts: 2
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("AI_LLM_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL_NAME", "env-gpt")
    monkeypatch.setenv("AI_TONE_MODEL_NAME", "env-tone")
    monkeypatch.setenv("AI_LIGHT_RULE_CHECK_MAX_REGEN_ATTEMPTS", "7")
    monkeypatch.setenv("AI_OPENAI_API_KEY", "secret-from-env")

    settings = _build_settings(config_path)

    assert settings.llm_provider == "openai"
    assert settings.model_name == "env-gpt"
    assert settings.tone_model_name == "env-tone"
    assert settings.light_rule_check_max_regen_attempts == 7
    assert settings.openai_api_key == "secret-from-env"
