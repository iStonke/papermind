import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ORMModel


NoteSearchScope = Literal["all", "title", "body"]


class NoteCreateRequest(BaseModel):
    """Neue Notiz. Beides optional → leere Notiz (Sofort-Anlegen)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=500)
    body_json: dict[str, Any] | None = None


class NoteUpdateRequest(BaseModel):
    """Teilaktualisierung (Autosave). Nur gesetzte Felder werden geschrieben."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=500)
    body_json: dict[str, Any] | None = None


class NoteListItem(ORMModel):
    """Schlanker Listeneintrag – ohne body_json, mit Vorschautext."""

    id: uuid.UUID
    title: str
    preview: str
    is_deleted: bool = False
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    items: list[NoteListItem]


class NoteRead(ORMModel):
    """Detail inkl. body_json (zum Öffnen im Editor)."""

    id: uuid.UUID
    title: str
    body_json: dict[str, Any]
    is_deleted: bool = False
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class NoteTextGenerationRequest(BaseModel):
    """Natural-language writing request from the note editor.

    ``document_context`` is reserved for an explicitly local-only path. Any
    non-empty value forces the backend to Ollama, regardless of the configured
    text provider.
    """

    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=2000)
    note_context: str = Field(default="", max_length=12000)
    selected_text: str = Field(default="", max_length=8000)
    document_context: str = Field(default="", max_length=16000)


class AIProviderCredentialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["openai", "anthropic"]
    api_key: str = Field(min_length=10, max_length=500)


class AIProviderCredentialStatus(BaseModel):
    configured: bool = False
    source: Literal["stored", "environment", "none"] = "none"
    masked: str = ""


class AICredentialsStatus(BaseModel):
    encryption_configured: bool = False
    openai: AIProviderCredentialStatus = Field(default_factory=AIProviderCredentialStatus)
    anthropic: AIProviderCredentialStatus = Field(default_factory=AIProviderCredentialStatus)
