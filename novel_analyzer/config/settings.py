"""Application settings."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_prefix="NOVEL_ANALYZER_",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
    )

    database_url: str = Field(default="")
    db_dialect: str = Field(default="sqlite")
    db_host: str = Field(default="127.0.0.1")
    db_port: int = Field(default=5432)
    db_user: str = Field(default="")
    db_password: str = Field(default="")
    db_name: str = Field(default="novel_analyzer")
    db_admin_name: str = Field(default="postgres")
    db_echo: bool = Field(default=False)

    llm_provider_name: str = Field(default="vip1129")
    llm_base_url: str = Field(default="")
    llm_api_key: str = Field(default="")
    llm_provider_vip1129_base_url: str = Field(default="https://api.vip1129.cc/v1")
    llm_provider_vip1129_api_key: str = Field(default="")
    llm_provider_vibediary_base_url: str = Field(default="https://vibediary.app/api/v1")
    llm_provider_vibediary_api_key: str = Field(default="")
    llm_model_name: str = Field(default="gpt-5.4")
    llm_stage_model_name: str = Field(default="gpt-5.1")
    llm_qa_model_name: str = Field(default="gpt-5.2")
    llm_fallback_model_name: str = Field(default="gpt-5.4")
    llm_timeout_seconds: float = Field(default=60.0)
    llm_max_retries: int = Field(default=2)
    cross_chapter_window: int = Field(default=5)
    chapter_splitter_version: str = Field(default="heuristic-v1")
    skills_dir: str = Field(default="skills_dir")
    skill_default_timeout: int = Field(default=30)
    embedding_model_name: str = Field(default="BAAI/bge-m3")
    embedding_backend: str = Field(default="onnx")
    embedding_model_path: str = Field(default="")
    embedding_cache_dir: str = Field(default=".cache/embeddings")
    embedding_max_length: int = Field(default=2048)
    embedding_stub_dim: int = Field(default=16)
    rerank_model_name: str = Field(default="")
    gate_model_name: str = Field(default="")

    @property
    def resolved_database_url(self) -> str:
        """Return the effective SQLAlchemy URL."""

        if self.database_url:
            return self.database_url
        if self.db_dialect == "sqlite":
            return "sqlite:///./novel_analyzer.db"
        password = quote_plus(self.db_password)
        return (
            f"postgresql+psycopg://{self.db_user}:{password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def admin_database_url(self) -> str:
        """Return an admin URL for PostgreSQL database creation checks."""

        if self.db_dialect != "postgresql":
            return self.resolved_database_url
        password = quote_plus(self.db_password)
        return (
            f"postgresql+psycopg://{self.db_user}:{password}@"
            f"{self.db_host}:{self.db_port}/{self.db_admin_name}"
        )

    @property
    def resolved_llm_base_url(self) -> str:
        """Return the active LLM relay base URL."""

        if self.llm_base_url:
            return self.llm_base_url
        if self.llm_provider_name == "vibediary":
            return self.llm_provider_vibediary_base_url
        return self.llm_provider_vip1129_base_url

    @property
    def resolved_llm_api_key(self) -> str:
        """Return the active LLM relay API key."""

        if self.llm_api_key:
            return self.llm_api_key
        if self.llm_provider_name == "vibediary":
            return self.llm_provider_vibediary_api_key
        return self.llm_provider_vip1129_api_key

    @property
    def masked_database_url(self) -> str:
        """Return a safe database URL for logs."""

        if self.database_url:
            if self.db_password:
                return self.database_url.replace(self.db_password, "***")
            return self.database_url
        if self.db_dialect == "sqlite":
            return self.resolved_database_url
        return (
            f"postgresql+psycopg://{self.db_user}:***@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings."""

    return Settings()
