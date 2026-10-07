import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Feste Bedeutungen der Lernmarkierungen (nicht konfigurierbar):
# Gelb = wichtig, Blau = Definition, Rot = unklar.
NOTE_LEARN_HIGHLIGHT_COLORS = ("important", "definition", "unclear")


class NoteLearnHighlight(Base):
    """Lernmarkierung in einem PDF, die zu genau einer Notiz gehört.

    Bewusst getrennt von ``annotations`` (Lesemodus): Diese Ebene entsteht in der
    Split-Ansicht Notiz↔Dokument. ``rects`` hat dasselbe normalisierte,
    rotationsfreie Format wie die Lesemodus-Markierungen.
    """

    __tablename__ = "note_learn_highlight"
    __table_args__ = (
        CheckConstraint(
            "color IN ('important', 'definition', 'unclear')",
            name="ck_note_learn_highlight_color",
        ),
        CheckConstraint("page >= 1", name="ck_note_learn_highlight_page"),
        Index("ix_note_learn_highlight_document_page", "document_id", "page"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("note.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False)
    rects: Mapped[list] = mapped_column(JSONB, nullable=False)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
