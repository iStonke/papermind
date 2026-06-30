import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Annotation(Base):
    """Markierung/Notiz/Verknüpfung auf einer Dokumentseite.

    Kind-Tabelle von ``documents`` – der Owner wird über das Parent-Dokument
    abgeleitet (RLS-Policy ``annotations_owner_isolation``), darum trägt die
    Tabelle KEINE eigene ``owner_id``. Das Original-PDF bleibt unangetastet:
    Markierungen werden ausschließlich als Overlay über der gerenderten Seite
    gezeichnet, verankert über ``rects`` (normalisierte 0–1-Rechtecke) plus den
    Textanker ``quote``/``prefix``/``suffix`` (Reanker-Fallback).
    """

    __tablename__ = "annotations"
    __table_args__ = (
        Index("ix_annotations_document_id", "document_id"),
        Index("ix_annotations_document_page", "document_id", "page"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    page: Mapped[int] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="highlight", server_default="highlight")
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    rects: Mapped[list] = mapped_column(JSONB, nullable=False)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    suffix: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Verknüpfungsziel (Stufe B/Phase 4) – ein anderes Dokument oder eine externe URL.
    target_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="annotations",
        foreign_keys=[document_id],
        lazy="select",
    )
