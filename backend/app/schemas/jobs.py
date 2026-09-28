import uuid
from datetime import datetime
from enum import Enum

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class JobActivityBackup(BaseModel):
    """Zustand des letzten NAS-Backups für die Header-Aktivitätsanzeige.

    Wird nur befüllt, wenn das Backup aktiviert ist und der zuletzt gestartete
    Lauf fehlgeschlagen ist – damit ein Backup-Problem sofort im Header sichtbar
    wird, ohne dass man die Einstellungen öffnen muss.
    """

    status: str
    error: str | None = None
    finished_at: datetime | None = None


class OcrBacklog(BaseModel):
    """Dokument-Ebene: wie viele Dokumente schon durchsuchbar (OCR) sind.

    Anders als ``summary`` (Einzeljobs) zeigt das den Gesamtfortschritt, auch in
    den Pausen zwischen den OCR-Häppchen, wenn gerade kein Job läuft.
    """

    total: int = 0
    done: int = 0
    pending: int = 0
    failed: int = 0


NoteAudioVoice = Literal["standard", "neutral", "amused", "sleepy", "whisper"]


class NoteAudioExportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=60_000)
    title: str = Field(default="", max_length=500)
    voice: NoteAudioVoice = "standard"

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("text must contain readable characters")
        return normalized


class NoteAudioExportRead(BaseModel):
    id: uuid.UUID
    note_id: uuid.UUID
    note_title: str
    filename: str
    voice: NoteAudioVoice
    status: Literal["queued", "running", "done", "failed"]
    progress: int = Field(ge=0, le=100)
    phase: str | None = None
    error_message: str | None = None
    cancel_requested: bool = False
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    downloaded_at: datetime | None = None


class JobActivityResponse(BaseModel):
    summary: JobActivitySummary
    jobs: list[JobActivityItem]
    audio_exports: list[NoteAudioExportRead] = Field(default_factory=list)
    ocr_backlog: OcrBacklog = Field(default_factory=OcrBacklog)
    backup: JobActivityBackup | None = None
