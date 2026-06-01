from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PaperMind Backend"
    app_version: str = "0.8.0"
    api_prefix: str = "/api"

    backend_port: int = 8000
    database_url: str = Field(default="")
    ai_base_url: str = Field(default="http://ai:11434")
    storage_path: str = Field(default="/data/storage")
    public_web_base_url: str = Field(default="")
    upload_max_bytes: int = Field(default=25 * 1024 * 1024)
    cors_allow_origins: str = Field(default="")
    auto_ocr_on_upload: bool = Field(default=True)
    min_text_chars: int = Field(default=300, ge=1)
    text_check_pages: int = Field(default=2, ge=1)
    worker_poll_interval_seconds: int = Field(default=3)
    worker_ocr_timeout_seconds: int = Field(default=900)
    # Periodischer OCR-Backfill: schließt regelmäßig Lücken (Dokumente ohne OCR).
    ocr_backfill_interval_seconds: int = Field(default=3600, ge=60)
    ocr_backfill_batch_size: int = Field(default=10, ge=1, le=200)
    ocr_backfill_max_retries: int = Field(default=3, ge=0)
    import_inbox_drop_path: str = Field(default="")
    import_inbox_file_stable_seconds: int = Field(default=3, ge=1, le=120)
    search_query_max_length: int = Field(default=256)
    fts_language: Literal["german", "simple"] = Field(default="german")
    index_auto_on_ready: bool = Field(default=True)
    embed_model: str = Field(default="hash-384-v1")
    embed_dim: int = Field(default=384, ge=8)
    embed_batch_size: int = Field(default=32, ge=1, le=256)
    chunk_size_chars: int = Field(default=1000, ge=200)
    chunk_overlap_chars: int = Field(default=100, ge=0)
    ai_embed_timeout_seconds: float = Field(default=30.0, gt=0.0)
    ai_chat_timeout_seconds: float = Field(default=60.0, gt=0.0)
    retrieval_max_top_k: int = Field(default=20, ge=1, le=100)
    dedupe_candidate_limit: int = Field(default=200, ge=10, le=2000)
    dedupe_text_distance_threshold: int = Field(default=6, ge=0, le=64)
    direct_upload_api_key: str = Field(default="")

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_allow_origins.strip()
        if not raw:
            return []
        if raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def fts_regconfig(self) -> str:
        return f"pg_catalog.{self.fts_language}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
