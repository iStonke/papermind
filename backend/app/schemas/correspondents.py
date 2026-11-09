import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.services.utils import (
    CORRESPONDENT_NAME_MAX_LENGTH,
    CORRESPONDENT_NAME_MIN_LENGTH,
    validate_correspondent_alias,
    validate_correspondent_name,
)

CORRESPONDENT_KINDS = {"organization", "person", "collection"}


def _normalize_kind(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip().lower()
    if not normalized:
        return None
    if normalized not in CORRESPONDENT_KINDS:
        raise ValueError("Correspondent kind must be organization, person or collection")
    return normalized


class CorrespondentCreateRequest(BaseModel):
    name: str = Field(min_length=CORRESPONDENT_NAME_MIN_LENGTH, max_length=CORRESPONDENT_NAME_MAX_LENGTH)
    first_name: str | None = Field(default=None, max_length=CORRESPONDENT_NAME_MAX_LENGTH)
    last_name: str | None = Field(default=None, max_length=CORRESPONDENT_NAME_MAX_LENGTH)
    short_name: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)
    kind: str | None = Field(default=None, description="organization | person | collection")
    parent_id: uuid.UUID | None = Field(default=None, description="Übergeordneter Eintrag: Organisation/Sammlung einer Person, Sammlung einer Organisation")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return validate_correspondent_name(value)

    @field_validator("kind")
    @classmethod
    def normalize_kind(cls, value: str | None) -> str | None:
        return _normalize_kind(value)

    @field_validator("first_name", "last_name", "short_name", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None


class CorrespondentAliasCreateRequest(BaseModel):
    alias: str = Field(min_length=1, max_length=120)

    @field_validator("alias")
    @classmethod
    def normalize_alias(cls, value: str) -> str:
        return validate_correspondent_alias(value)


class CorrespondentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=CORRESPONDENT_NAME_MIN_LENGTH, max_length=CORRESPONDENT_NAME_MAX_LENGTH)
    first_name: str | None = Field(default=None, max_length=CORRESPONDENT_NAME_MAX_LENGTH)
    last_name: str | None = Field(default=None, max_length=CORRESPONDENT_NAME_MAX_LENGTH)
    short_name: str | None = Field(default=None, max_length=60)
    notes: str | None = Field(default=None, max_length=2000)
    kind: str | None = Field(default=None, description="organization | person | collection")
    parent_id: uuid.UUID | None = Field(default=None, description="Übergeordneter Eintrag (null löst die Zuordnung)")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_correspondent_name(value)

    @field_validator("kind")
    @classmethod
    def normalize_kind(cls, value: str | None) -> str | None:
        return _normalize_kind(value)

    @field_validator("first_name", "last_name", "short_name", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None


class CorrespondentMatcherCreateRequest(BaseModel):
    kind: str = Field(default="contains")
    pattern: str = Field(min_length=1, max_length=240)
    scope: str = Field(default="both")
    priority: int = Field(default=100, ge=0, le=1000)

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        normalized = " ".join(str(value or "").split()).strip() or "contains"
        if normalized not in {"contains", "regex", "starts_with"}:
            raise ValueError("Matcher kind must be contains, regex or starts_with")
        return normalized

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        normalized = " ".join(str(value or "").split()).strip() or "both"
        if normalized not in {"filename", "ocr_text", "both"}:
            raise ValueError("Matcher scope must be filename, ocr_text or both")
        return normalized

    @field_validator("pattern")
    @classmethod
    def normalize_pattern(cls, value: str) -> str:
        normalized = " ".join(value.split()).strip()
        if not normalized:
            raise ValueError("Matcher pattern must not be empty")
        return normalized


class CorrespondentAliasRead(ORMModel):
    id: uuid.UUID
    alias: str


class CorrespondentMatcherRead(ORMModel):
    id: uuid.UUID
    kind: str
    pattern: str
    scope: str
    priority: int


class CorrespondentRead(ORMModel):
    id: uuid.UUID
    name: str
    first_name: str | None = None
    last_name: str | None = None
    short_name: str | None = None
    notes: str | None = None
    kind: str | None = None
    parent_id: uuid.UUID | None = None
    parent_name: str | None = None
    created_at: datetime
    aliases: list[CorrespondentAliasRead] = Field(default_factory=list)
    matchers: list[CorrespondentMatcherRead] = Field(default_factory=list)
    usage_count: int | None = None
    last_document_date: date | None = None


class CorrespondentMergeRequest(BaseModel):
    source_id: uuid.UUID = Field(description="Eintrag, der im Ziel aufgeht und danach gelöscht wird")


class CorrespondentMergeResponse(BaseModel):
    correspondent: CorrespondentRead
    documents: int
    aliases: int
    matchers: int
    relations: int
    members: int
    notes: int


class CorrespondentListResponse(BaseModel):
    items: list[CorrespondentRead]


class CorrespondentProfileMember(BaseModel):
    id: uuid.UUID
    name: str
    kind: str | None = None
    document_count: int = 0
    last_document_date: date | None = None


class CorrespondentAmountSummary(BaseModel):
    currency: str | None = None
    total: Decimal
    count: int


class CorrespondentProfileActivity(BaseModel):
    """Ein Dokument als Datenpunkt der Profilgrafiken (ohne Inhalte)."""

    document_date: date
    correspondent_id: uuid.UUID
    document_type: str | None = None


# Rolle des *anderen* Korrespondenten aus Sicht des Profils.
CORRESPONDENT_RELATION_ROLES = ("predecessor", "successor", "acts_for", "agent")


class CorrespondentRelationCreateRequest(BaseModel):
    """predecessor/successor: der andere ist Vorgänger/Nachfolger; acts_for:
    dieser Korrespondent handelt für den anderen; agent: der andere handelt
    für diesen."""

    role: str
    other_id: uuid.UUID

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        role = str(value or "").strip()
        if role not in CORRESPONDENT_RELATION_ROLES:
            raise ValueError(f"Unbekannte Verbindung: {role}")
        return role


class CorrespondentRelationRead(BaseModel):
    """Eine Verbindung aus Sicht des Profils inkl. Kennzahlen des Gegenübers."""

    id: uuid.UUID
    role: str
    other_id: uuid.UUID
    other_name: str
    other_kind: str | None = None
    document_count: int = 0
    first_document_date: date | None = None
    last_document_date: date | None = None


class CorrespondentProfileRead(BaseModel):
    """Kennzahlen der Profilseite; bei Organisationen inkl. zugeordneter Personen."""

    correspondent: CorrespondentRead
    document_count: int = 0
    own_document_count: int = 0
    first_document_date: date | None = None
    last_document_date: date | None = None
    members: list[CorrespondentProfileMember] = Field(default_factory=list)
    amount_year: int
    amounts: list[CorrespondentAmountSummary] = Field(default_factory=list)
    # Alle Dokumente (aufsteigend nach Datum) für Jahres-/Monats-/Typverteilung.
    activity: list[CorrespondentProfileActivity] = Field(default_factory=list)
    relations: list[CorrespondentRelationRead] = Field(default_factory=list)


class UnresolvedCorrespondentItemRead(BaseModel):
    document_id: uuid.UUID
    title: str
    original_filename: str
    sender: str | None = None
    document_type: str | None = None
    document_date: str | None = None
    ai_status: str
    ocr_status: str
    text_available: bool
    text_excerpt: str | None = None


class UnresolvedCorrespondentReportResponse(BaseModel):
    scanned: int
    unresolved: int
    include_deleted: bool
    items: list[UnresolvedCorrespondentItemRead]


class CorrespondentReviewIgnoreRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split()).strip()
        return normalized or None
