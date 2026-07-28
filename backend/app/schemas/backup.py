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
    retention_daily: int | None = Field(default=None, ge=1, le=365)
    retention_weekly: int | None = Field(default=None, ge=0, le=260)
    retention_monthly: int | None = Field(default=None, ge=0, le=120)
    secondary_enabled: bool | None = None
    secondary_nas_host: str | None = Field(default=None, max_length=255)
    secondary_nas_share: str | None = Field(default=None, max_length=255)
    secondary_nas_folder: str | None = Field(default=None, max_length=255)
    secondary_nas_username: str | None = Field(default=None, max_length=255)
    secondary_nas_password: str | None = Field(default=None, max_length=255)

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

    @field_validator(
        "nas_host",
        "nas_share",
        "nas_folder",
        "nas_username",
        "secondary_nas_host",
        "secondary_nas_share",
        "secondary_nas_folder",
        "secondary_nas_username",
    )
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
    last_restore_test_at: datetime | None = None


class BackupTestResponse(BaseModel):
    ok: bool
    message: str


class BackupRunStartResponse(BaseModel):
    started: bool
    message: str | None = None


class BackupArchiveItem(BaseModel):
    name: str
    size_bytes: int = 0
    created_at: datetime | None = None
    complete: bool = True
    verified: bool = False
    encrypted: bool = False
    format_version: int | None = None


class BackupArchiveListResponse(BaseModel):
    items: list[BackupArchiveItem] = Field(default_factory=list)


class BackupRestoreRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        import re

        normalized = str(value).strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}_\d{6}$", normalized):
            raise ValueError("name must be a backup timestamp folder (YYYY-MM-DD_HHMMSS)")
        return normalized


class BackupRestoreStatusResponse(BaseModel):
    status: str | None = None
    name: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    verified_at: datetime | None = None
    safety_backup: str | None = None
