import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class JobType(str, Enum):
    OCR = "OCR"
    INDEX = "INDEX"
    EMBED = "EMBED"
    TAG = "TAG"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class JobCreateRequest(BaseModel):
    type: JobType


class JobUpdateRequest(BaseModel):
    status: JobStatus | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    error_message: str | None = Field(default=None, max_length=4000)


class JobRead(ORMModel):
    id: uuid.UUID
    document_id: uuid.UUID
    type: JobType
    status: JobStatus
    progress: int | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    items: list[JobRead]


class JobActivityItem(JobRead):
    """Ein Job inkl. Dokumenttitel für die Aktivitäts-Anzeige im Header."""

    document_title: str | None = None


class JobActivitySummary(BaseModel):
    queued: int = 0
    running: int = 0
    failed: int = 0


class JobActivityResponse(BaseModel):
    summary: JobActivitySummary
    jobs: list[JobActivityItem]
