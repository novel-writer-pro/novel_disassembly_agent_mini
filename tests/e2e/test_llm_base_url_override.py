from __future__ import annotations

import pytest

from novel_analyzer.config.settings import Settings, get_settings
from novel_analyzer.llm.client import build_chat_model


@pytest.fixture(autouse=True)
def reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings_with(**overrides) -> Settings:
    base = {
        "llm_base_url": "https://api.upstream.example/v1",
        "llm_model_name": "test-model",
        "llm_api_key": "sk-test",
    }
    base.update(overrides)
    return Settings(**base)


def test_no_override_uses_resolved_base_url():
    settings = _settings_with()
    chat = build_chat_model(settings)
    assert str(chat.openai_api_base).rstrip("/") == "https://api.upstream.example/v1"


def test_override_replaces_base_url():
    settings = _settings_with(
        llm_base_url_override="http://localhost:8585/v1/openai",
    )
    chat = build_chat_model(settings)
    assert str(chat.openai_api_base).rstrip("/") == "http://localhost:8585/v1/openai"


def test_empty_string_override_acts_like_unset():
    settings = _settings_with(llm_base_url_override="")
    chat = build_chat_model(settings)
    assert str(chat.openai_api_base).rstrip("/") == "https://api.upstream.example/v1"


def test_override_takes_precedence_over_explicit_base_url():
    settings = _settings_with(
        llm_base_url="https://api.original.example/v1",
        llm_base_url_override="http://localhost:8585/v1/openai",
    )
    chat = build_chat_model(settings)
    assert "8585" in str(chat.openai_api_base)
