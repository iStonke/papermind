import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NoteCollection(Base):
    """Sammlung – oberste, owner-scoped Ebene der Notizenverwaltung.

    Anders als das Notizbuch (Ablage) oder Tags (Querachse) ist die Sammlung
    eine **harte Partition**: wenige, grobe Arbeitsbereiche (z. B. „Studium",
    „Arbeit"), zwischen denen der Nutzer wie zwischen getrennten Räumen wechselt.
    Modell ``Sammlung → Notizbuch → Notiz``: ``note.collection_id`` ist die
    Wahrheitsquelle, ``note_notebook.collection_id`` spiegelt sie.

    Vorlagen sind bewusst sammlungsübergreifend (``note.collection_id = NULL``);
    ein partieller CHECK erzwingt die Zugehörigkeit nur für Nicht-Vorlagen.
    """

    __tablename__ = "note_collection"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_note_collection_owner_name"),
        Index("ix_note_collection_owner", "owner_id", "position", "name"),
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
