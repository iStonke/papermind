import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Correspondent(Base):
    """Kanonischer Korrespondent (Absender/Aussteller eines Dokuments).

    ``Document.ai_sender`` bleibt der rohe LLM-Befund; der kanonische
    Korrespondent wird über Aliase und Matcher aufgelöst und als
    ``Document.correspondent_id`` verknüpft.
    """

    __tablename__ = "correspondents"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_correspondents_owner_name"),
        Index("ix_correspondents_owner_name", "owner_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    aliases: Mapped[list["CorrespondentAlias"]] = relationship(
        "CorrespondentAlias",
        back_populates="correspondent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    matchers: Mapped[list["CorrespondentMatcher"]] = relationship(
        "CorrespondentMatcher",
        back_populates="correspondent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CorrespondentAlias(Base):
    """Alternative Schreibweise eines Korrespondenten für die exakte Auflösung."""

    __tablename__ = "correspondent_aliases"
    __table_args__ = (
        # Pro Korrespondent ist ein Alias case-insensitiv eindeutig.
        Index(
            "uq_correspondent_aliases_lower",
            "correspondent_id",
            text("lower(alias)"),
            unique=True,
        ),
        Index("ix_correspondent_aliases_correspondent_id", "correspondent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correspondent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("correspondents.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(Text, nullable=False)

    correspondent: Mapped["Correspondent"] = relationship("Correspondent", back_populates="aliases")


class CorrespondentMatcher(Base):
    """Regel, die rohe Texte (Absender, Dateiname, OCR) auf einen Korrespondenten abbildet."""

    __tablename__ = "correspondent_matchers"
    __table_args__ = (
        Index("ix_correspondent_matchers_correspondent_id", "correspondent_id"),
        Index("ix_correspondent_matchers_priority", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correspondent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("correspondents.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="contains")
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="both")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")

    correspondent: Mapped["Correspondent"] = relationship("Correspondent", back_populates="matchers")
