import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ORMModel


NoteSearchScope = Literal["all", "title", "body"]
NoteHistoryReason = Literal[
    "created",
    "autosave",
    "navigation",
    "export",
    "ai",
    "before_restore",
    "restore",
    "manual",
]


class NoteTagRef(ORMModel):
    """Tag-Referenz (aus der gemeinsamen ``tags``-Tabelle) an einer Notiz."""

    id: uuid.UUID
    name: str


class NoteTagsUpdateRequest(BaseModel):
    """Setzt die Tags einer Notiz.

    ``tag_ids`` verknüpft bestehende Tags (Editor-Picker liefert IDs), ``tags``
    erlaubt zusätzlich Namen (unbekannte werden angelegt – für Bulk/KI). Beide
    werden vereinigt; die Notiz trägt danach genau diese Tags.
    """

    model_config = ConfigDict(extra="forbid")

    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=50)


class NoteCreateRequest(BaseModel):
    """Neue Notiz. Beides optional → leere Notiz (Sofort-Anlegen)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=500)
    body_json: dict[str, Any] | None = None
    is_template: bool = False


NoteBulkAction = Literal["trash", "restore", "delete", "template"]


class NoteBulkRequest(BaseModel):
    """Sammelaktion des Verwaltungsrasters über mehrere Notizen.

    ``template`` leitet aus jeder ausgewählten Notiz eine neue Vorlage ab
    (Originale bleiben bestehen), ``delete`` löscht endgültig.
    """

    model_config = ConfigDict(extra="forbid")

    action: NoteBulkAction
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class NoteBulkResult(BaseModel):
    ok: bool = True
    affected: int = 0


class SaveAsTemplateRequest(BaseModel):
    """Aus einer bestehenden Notiz eine (neue) Vorlage ableiten."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=500)


# --- Baustein-Vorlagen (Feldblöcke) ------------------------------------------
class NoteBlockTemplateField(BaseModel):
    """Eine Feldzeile einer Baustein-Vorlage."""

    model_config = ConfigDict(extra="ignore")

    label: str = Field(default="", max_length=200)
    hint: str = Field(default="", max_length=200)


class NoteBlockTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", max_length=200)
    title: str = Field(default="", max_length=200)
    color: str = Field(default="teal", max_length=32)
    fields: list[NoteBlockTemplateField] = Field(default_factory=list)


class NoteBlockTemplateUpdateRequest(BaseModel):
    """Teilaktualisierung. Nur gesetzte Felder werden geschrieben."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    color: str | None = Field(default=None, max_length=32)
    fields: list[NoteBlockTemplateField] | None = None


class NoteBlockTemplateRead(ORMModel):
    id: uuid.UUID
    name: str
    title: str
    color: str
    fields: list[NoteBlockTemplateField]
    created_at: datetime
    updated_at: datetime


class NoteBlockTemplateListResponse(BaseModel):
    items: list[NoteBlockTemplateRead]


class NoteUpdateRequest(BaseModel):
    """Teilaktualisierung (Autosave). Nur gesetzte Felder werden geschrieben."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=500)
    body_json: dict[str, Any] | None = None
    # Ist die Serverrevision inzwischen weiter, darf ein älterer Browserstand
    # nicht still darübergeschrieben werden. Optional für ältere API-Clients.
    base_revision: int | None = Field(default=None, ge=1)
    # Autosaves werden zeitlich gebündelt; bewusste KI-Übernahmen bilden einen
    # eigenen, beschrifteten Wiederherstellungspunkt.
    history_reason: Literal["autosave", "ai", "manual"] = "autosave"


class NoteRevisionCheckpointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["navigation", "export", "manual"]


class NoteRevisionRestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_revision: int = Field(ge=1)


class NoteRevisionListItem(ORMModel):
    id: uuid.UUID
    note_id: uuid.UUID
    note_revision: int
    reason: NoteHistoryReason
    title: str
    preview: str = ""
    created_at: datetime
    updated_at: datetime


class NoteRevisionRead(ORMModel):
    id: uuid.UUID
    note_id: uuid.UUID
    note_revision: int
    reason: NoteHistoryReason
    title: str
    body_json: dict[str, Any]
    body_text: str = ""
    created_at: datetime
    updated_at: datetime


class NoteRevisionListResponse(BaseModel):
    items: list[NoteRevisionListItem]
    total: int = 0


class NoteListItem(ORMModel):
    """Schlanker Listeneintrag – ohne body_json, mit Vorschautext.

    ``link_count`` summiert aus- und eingehende Verweise (note_link) und speist
    im Verwaltungsraster die Facette „Verwaist" (link_count == 0) sowie den
    Verknüpfungs-Chip. Vorlagen erzeugen keine Verweise, hier bleibt der Wert 0.
    """

    id: uuid.UUID
    title: str
    preview: str
    is_template: bool = False
    is_deleted: bool = False
    deleted_at: datetime | None = None
    link_count: int = 0
    tags: list[NoteTagRef] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class NoteListResponse(BaseModel):
    items: list[NoteListItem]


class NoteRead(ORMModel):
    """Detail inkl. body_json (zum Öffnen im Editor)."""

    id: uuid.UUID
    title: str
    body_json: dict[str, Any]
    revision: int = 1
    is_template: bool = False
    is_deleted: bool = False
    deleted_at: datetime | None = None
    tags: list[NoteTagRef] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class NoteImageRead(ORMModel):
    """Metadata returned after a successful note-image upload."""

    id: uuid.UUID
    note_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    src: str


class NoteTextGenerationRequest(BaseModel):
    """Natural-language writing request from the note editor.

    ``document_context`` is reserved for an explicitly local-only path. Any
    non-empty value forces the backend to Ollama, regardless of the configured
    text provider.
    """

    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=2000)
    length_instruction: str = Field(default="", max_length=120)
    note_context: str = Field(default="", max_length=12000)
    context_scope: Literal["before", "note"] = "before"
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
