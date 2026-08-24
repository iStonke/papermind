import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Note(Base):
    """Born-digital Notiz als erstklassiges, owner-scoped Objekt.

    `body_json` (ProseMirror) ist die Quelle der Wahrheit; `body_text` wird im
    Service daraus abgeleitet und speist `search_vector` (DB-Trigger).
    """

    __tablename__ = "note"
    __table_args__ = (
        Index("ix_note_owner_updated", "owner_id", "updated_at"),
        Index("ix_note_owner_deleted_updated", "owner_id", "is_deleted", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    body_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    body_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class NoteLink(Base):
    """Denormalisierter Verweis einer Notiz auf ein anderes Objekt.

    Beim Speichern aus `Note.body_json` neu berechnet (Service). Ermöglicht
    schnelle Rückverweise ohne rekursive JSONB-Suche.
    """

    __tablename__ = "note_link"
    __table_args__ = (
        Index("ix_note_link_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("note.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)  # document|correspondent|dossier|note
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
