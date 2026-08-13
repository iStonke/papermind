from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WikiPageKind(str, Enum):
    source = "source"
    entity = "entity"
    contract = "contract"
    topic = "topic"
    timeline = "timeline"
    comparison = "comparison"
    analysis = "analysis"


class WikiPageStatus(str, Enum):
    active = "active"
    needs_review = "needs_review"
    stale = "stale"
    archived = "archived"


class WikiClaimType(str, Enum):
    fact = "fact"
    inference = "inference"
    user_assertion = "user_assertion"


class WikiClaimStatus(str, Enum):
    active = "active"
    needs_review = "needs_review"
    disputed = "disputed"
    superseded = "superseded"
    retracted = "retracted"
    stale = "stale"


class WikiEvidenceRole(str, Enum):
    supports = "supports"
    contradicts = "contradicts"


class WikiEvidenceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: uuid.UUID
    chunk_id: uuid.UUID
    quote: str = Field(min_length=1, max_length=4000)
    support_role: WikiEvidenceRole = WikiEvidenceRole.supports

    @field_validator("quote")
    @classmethod
    def normalize_quote(cls, value: str) -> str:
        normalized = " ".join(str(value or "").split()).strip()
        if not normalized:
            raise ValueError("quote must not be empty")
        return normalized


class WikiClaimCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stable_key: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=8000)
    subject: str | None = Field(default=None, max_length=1000)
    predicate: str | None = Field(default=None, max_length=80)
    object_text: str | None = Field(default=None, max_length=4000)
    claim_type: WikiClaimType = WikiClaimType.fact
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    valid_from: date | None = None
    valid_to: date | None = None
    evidence: list[WikiEvidenceCandidate] = Field(default_factory=list, max_length=20)

    @field_validator("stable_key")
    @classmethod
    def normalize_stable_key(cls, value: str) -> str:
        normalized = "-".join(str(value or "").strip().lower().split())
        if not normalized:
            raise ValueError("stable_key must not be empty")
        return normalized

    @field_validator("text", "subject", "predicate", "object_text")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_dates(self) -> "WikiClaimCandidate":
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        return self


class WikiEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    page_from: int | None = None
    page_to: int | None = None
    quote: str
    support_role: WikiEvidenceRole
    chunk_content_hash: str
    document_text_hash: str | None = None
    valid: bool = True
    document_title: str | None = None


class WikiClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    revision_id: uuid.UUID
    stable_key: str
    text: str
    subject: str | None = None
    predicate: str | None = None
    object_text: str | None = None
    claim_type: WikiClaimType
    status: WikiClaimStatus
    confidence: float | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    supersedes_claim_id: uuid.UUID | None = None
    source_document_id: uuid.UUID | None = None
    locked_by_user: bool = False
    created_by: str
    created_at: datetime
    updated_at: datetime
    evidence: list[WikiEvidenceRead] = Field(default_factory=list)


class WikiRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_id: uuid.UUID
    revision_number: int
    markdown: str
    content_hash: str
    based_on_revision_id: uuid.UUID | None = None
    schema_version: str
    prompt_version: str | None = None
    model_name: str | None = None
    created_by: str
    change_reason: str
    created_at: datetime


class WikiPageListItem(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    kind: WikiPageKind
    status: WikiPageStatus
    source_document_id: uuid.UUID | None = None
    current_revision_id: uuid.UUID | None = None
    active_claim_count: int = 0
    review_claim_count: int = 0
    conflict_claim_count: int = 0
    source_count: int = 0
    updated_at: datetime
    score: float | None = None
    snippet: str | None = None


class WikiPageListResponse(BaseModel):
    items: list[WikiPageListItem]
    total: int


class WikiLinkRead(BaseModel):
    id: uuid.UUID
    from_page_id: uuid.UUID
    to_page_id: uuid.UUID
    relation: str
    status: str
    linked_page_id: uuid.UUID
    linked_page_title: str
    linked_page_kind: WikiPageKind


class WikiPageDetail(WikiPageListItem):
    markdown: str
    current_revision: WikiRevisionRead | None = None
    claims: list[WikiClaimRead] = Field(default_factory=list)
    claim_total: int = 0
    links: list[WikiLinkRead] = Field(default_factory=list)
    revision_count: int = 0


class WikiClaimCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_id: uuid.UUID
    corrected_text: str = Field(min_length=1, max_length=8000)
    subject: str | None = Field(default=None, max_length=1000)
    predicate: str | None = Field(default=None, max_length=80)
    object_text: str | None = Field(default=None, max_length=4000)
    claim_type: WikiClaimType = WikiClaimType.fact
    valid_from: date | None = None
    valid_to: date | None = None
    evidence: list[WikiEvidenceCandidate] = Field(default_factory=list, max_length=20)
    lock_after_correction: bool = True
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("corrected_text", "reason", "subject", "predicate", "object_text")
    @classmethod
    def normalize_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None


class WikiClaimRetractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=1000)


class WikiProposalStatus(str, Enum):
    pending = "pending"
    validated = "validated"
    applied = "applied"
    rejected = "rejected"
    failed = "failed"


class WikiProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_document_id: uuid.UUID | None = None
    source_chat_session_id: uuid.UUID | None = None
    page_id: uuid.UUID | None = None
    base_revision_id: uuid.UUID | None = None
    applied_revision_id: uuid.UUID | None = None
    proposal_type: str
    status: WikiProposalStatus
    payload: dict[str, Any]
    validation_errors: list[dict[str, Any]] | None = None
    schema_version: str
    prompt_version: str | None = None
    model_name: str | None = None
    review_note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    applied_at: datetime | None = None


class WikiProposalListResponse(BaseModel):
    items: list[WikiProposalRead]
    total: int


class WikiProposalReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern="^(accept|reject)$")
    note: str | None = Field(default=None, max_length=2000)
    accepted_claims: list[WikiClaimCandidate] | None = Field(default=None, max_length=100)


class WikiCaptureAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: uuid.UUID
    message_id: uuid.UUID
    title: str = Field(min_length=1, max_length=240)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("title must not be empty")
        return normalized


class WikiLintIssue(BaseModel):
    code: str
    severity: str
    message: str
    page_id: uuid.UUID | None = None
    claim_id: uuid.UUID | None = None
    evidence_id: uuid.UUID | None = None


class WikiLintResponse(BaseModel):
    checked_pages: int
    checked_claims: int
    fixed_claims: int
    issues: list[WikiLintIssue]


class WikiBackfillResponse(BaseModel):
    processed: int
    updated: int
    review_proposals: int
    failed: int


class WikiBackfillControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern="^(pause|resume|cancel)$")


class WikiBackfillRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    batch_size: int
    document_limit: int | None = None
    total_documents: int
    processed_documents: int
    updated_documents: int
    review_proposals: int
    failed_documents: int
    current_document_id: uuid.UUID | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    progress: int = 0

    @model_validator(mode="after")
    def calculate_progress(self) -> "WikiBackfillRunRead":
        if self.status == "done":
            self.progress = 100
        elif self.total_documents <= 0:
            self.progress = 0
        else:
            self.progress = min(99, round(self.processed_documents * 100 / self.total_documents))
        return self


class WikiOverviewResponse(BaseModel):
    pages: int = 0
    active_claims: int = 0
    review_claims: int = 0
    disputed_claims: int = 0
    stale_claims: int = 0
    pending_proposals: int = 0
    source_coverage: int = 0
    source_total: int = 0
