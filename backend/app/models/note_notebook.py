import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NoteNotebook(Base):
    """Leichtes, owner-scoped Notizbuch – genau eine flache Ablageebene.

    Bewusst ohne ``parent_id``/Hierarchie: Notizbücher sind stabile Heimathäfen,
    die eigentliche Skalierung für viele Notizen leisten Tags, Verweise und
    gespeicherte Ansichten. Eine Notiz gehört zu höchstens einem Notizbuch
    (``note.notebook_id``); ``NULL`` heißt „Ohne Notizbuch".
    """

    __tablename__ = "note_notebook"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_note_notebook_owner_name"),
        Index("ix_note_notebook_owner", "owner_id", "position", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
