import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class RetentionStatus(str, Enum):
    not_evaluated = "not_evaluated"
    suggested = "suggested"
    accepted = "accepted"
    manual = "manual"


class RetentionPaperOriginal(str, Enum):
    unclear = "unclear"
    keep = "keep"
    scan_sufficient = "scan_sufficient"
    not_applicable = "not_applicable"


# period_years: None = unklar, -1 = unbegrenzt, sonst Jahre ab Dokumentdatum.
RETENTION_PERIOD_UNLIMITED = -1


class DocumentRetentionRead(ORMModel):
    document_id: uuid.UUID
    status: RetentionStatus = RetentionStatus.not_evaluated
    period_years: int | None = None
    retain_until: date | None = None
    paper_original: RetentionPaperOriginal = RetentionPaperOriginal.unclear
    reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentRetentionUpdateRequest(BaseModel):
    status: RetentionStatus = RetentionStatus.manual
    period_years: int | None = Field(default=None, ge=-1, le=100)
    paper_original: RetentionPaperOriginal = RetentionPaperOriginal.unclear
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None
