"""Application settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import SplitResult, quote_plus, urlsplit, urlunsplit

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
    db_dialect: str = Field(default="postgresql")
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
    chapter_failure_retry_limit: int = Field(default=5)
    chapter_job_stall_timeout_seconds: int = Field(default=180)
    cross_chapter_window: int = Field(default=5)
    chapter_splitter_version: str = Field(default="heuristic-v1")
    skills_dir: str = Field(default="skills_dir")
    skill_default_timeout: int = Field(default=30)
    embedding_model_name: str = Field(default="BAAI/bge-m3")
    embedding_backend: str = Field(default="onnx")
    embedding_model_path: str = Field(default="")
    embedding_cache_dir: str = Field(default=".cache/embeddings")
    runtime_cache_dir: str = Field(default=".cache/novel-analyzer")
    embedding_max_length: int = Field(default=2048)
    embedding_stub_dim: int = Field(default=16)
    rerank_model_name: str = Field(default="")
    gate_model_name: str = Field(default="")

    @property
    def resolved_database_url(self) -> str:
        """Return the effective SQLAlchemy URL."""

        if self.database_url:
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Only PostgreSQL database URLs are supported")
            return self.database_url
        password = quote_plus(self.db_password)
        return (
            f"postgresql+psycopg://{self.db_user}:{password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def effective_db_name(self) -> str:
        """Return the target database name, honoring explicit URLs."""

        if self.database_url:
            parts = urlsplit(self.database_url)
            return parts.path.lstrip("/") or self.db_name
        return self.db_name

    @property
    def admin_database_url(self) -> str:
        """Return an admin URL for PostgreSQL database creation checks."""

        if self.database_url:
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Only PostgreSQL database URLs are supported")
            parts = urlsplit(self.database_url)
            username = parts.username or ""
            password = f":{parts.password}" if parts.password else ""
            host = _netloc_without_auth(parts)
            auth = f"{username}{password}@" if username or password else ""
            return urlunsplit(
                (
                    parts.scheme,
                    f"{auth}{host}",
                    f"/{self.db_admin_name}",
                    parts.query,
                    parts.fragment,
                )
            )
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
            try:
                parts = urlsplit(self.database_url)
                if parts.password is None:
                    return self.database_url
                username = parts.username or ""
                host = _netloc_without_auth(parts)
                auth = f"{username}:***@{host}"
                return urlunsplit((parts.scheme, auth, parts.path, parts.query, parts.fragment))
            except ValueError:
                return self.database_url
        return (
            f"postgresql+psycopg://{self.db_user}:***@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def resolved_runtime_cache_dir(self) -> Path:
        """Return the managed runtime cache root."""

        return Path(self.runtime_cache_dir)

    @property
    def legacy_runtime_dir(self) -> Path:
        """Return the previous runtime root kept for compatibility/migration."""

        return Path(".omx")


def _netloc_without_auth(parts: SplitResult) -> str:
    """Return the original netloc stripped of any username/password prefix."""

    if "@" in parts.netloc:
        return parts.netloc.rsplit("@", 1)[1]
    return parts.netloc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings."""

    return Settings()
