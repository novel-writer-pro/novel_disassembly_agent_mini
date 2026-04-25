"""LLM client helpers."""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from novel_analyzer.config.settings import Settings, get_settings


def build_chat_model(
    settings: Settings | None = None,
    *,
    model_name: str | None = None,
) -> ChatOpenAI:
    """Create the configured ChatOpenAI client."""

    runtime = settings or get_settings()
    api_key_value = runtime.resolved_llm_api_key
    api_key = SecretStr(api_key_value) if api_key_value else None
    return ChatOpenAI(
        model=model_name or runtime.llm_model_name,
        base_url=runtime.resolved_llm_base_url,
        api_key=api_key,
        timeout=runtime.llm_timeout_seconds,
        max_retries=runtime.llm_max_retries,
    )
