import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NoteBlockTemplate(Base):
    """Benutzereigene Baustein-Vorlage für den Vorlagenfeld-Block (templateBox).

    Anders als ``Note.is_template`` (eine ganze Notiz als Gerüst) beschreibt dies
    einen wiederverwendbaren Feldblock: Titel, Farbe und Feldzeilen
    (``label`` + ``hint``). Erscheint im Slash-Menü und in der Vorlagen-Verwaltung
    und wird beim Einfügen zu einem ``templateBox``-Knoten expandiert.
    """

    __tablename__ = "note_block_template"
    __table_args__ = (
        Index("ix_note_block_template_owner_updated", "owner_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    color: Mapped[str] = mapped_column(String(32), nullable=False, server_default="teal")
    # Liste aus {"label": str, "hint": str} – die anfänglichen Feldzeilen.
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
