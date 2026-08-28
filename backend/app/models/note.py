import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.note_tag import note_tags


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
    # Monotone Inhaltsrevision für optimistisches Sperren im Notizeditor.
    # Tags/Papierkorbstatus zählen bewusst nicht dazu: geschützt werden die
    # gemeinsam per Autosave geschriebenen Felder Titel + body_json.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Gemeinsames Tag-Vokabular mit Dokumenten (dieselbe ``tags``-Tabelle).
    tags: Mapped[list["Tag"]] = relationship(  # noqa: F821
        "Tag", secondary=note_tags, lazy="selectin"
    )


class NoteRevision(Base):
    """Zeitlich gebündelter, wiederherstellbarer Inhaltsstand einer Notiz."""

    __tablename__ = "note_revision"
    __table_args__ = (
        CheckConstraint("note_revision > 0", name="ck_note_revision_number"),
        CheckConstraint(
            "reason IN ('created', 'autosave', 'navigation', 'export', 'ai', "
            "'before_restore', 'restore', 'manual')",
            name="ck_note_revision_reason",
        ),
        UniqueConstraint("note_id", "note_revision", name="uq_note_revision_note_number"),
        Index("ix_note_revision_note_updated", "note_id", "updated_at"),
        Index("ix_note_revision_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("note.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    note_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False, server_default="autosave")
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    body_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    body_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
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


class NoteTask(Base):
    """Denormalisierte Aufgabe (taskItem) einer Notiz.

    Beim Speichern aus `Note.body_json` neu berechnet (Service). Ermöglicht die
    Abfrage offener/fälliger Aufgaben über alle Notizen (Dashboard-Kachel).
    """

    __tablename__ = "note_task"
    __table_args__ = (
        Index("ix_note_task_open_due", "due_date", postgresql_where="NOT done"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("note.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
