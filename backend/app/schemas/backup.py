from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BackupConfigPatch(BaseModel):
    enabled: bool | None = None
    nas_host: str | None = Field(default=None, max_length=255)
    nas_share: str | None = Field(default=None, max_length=255)
    nas_folder: str | None = Field(default=None, max_length=255)
    nas_username: str | None = Field(default=None, max_length=255)
    nas_password: str | None = Field(default=None, max_length=255)
    frequency: str | None = None
    time: str | None = Field(default=None, max_length=5)
    weekday: int | None = Field(default=None, ge=0, le=6)
    retention: int | None = Field(default=None, ge=1, le=365)

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized not in {"daily", "weekly"}:
            raise ValueError("frequency must be 'daily' or 'weekly'")
        return normalized

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        import re

        if not re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", normalized):
            raise ValueError("time must be HH:MM (24h)")
        return normalized

    @field_validator("nas_host", "nas_share", "nas_folder", "nas_username")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class BackupStatusResponse(BaseModel):
    config: dict[str, Any]
    last_run: dict[str, Any] | None = None
    last_success_at: datetime | None = None
    next_run_at: datetime | None = None
    is_running: bool = False


class BackupTestResponse(BaseModel):
    ok: bool
    message: str


class BackupRunStartResponse(BaseModel):
    started: bool
    message: str | None = None
