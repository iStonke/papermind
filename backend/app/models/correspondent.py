import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
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
        Index("ix_correspondents_parent_id", "parent_id"),
        # Erlaubte Typen (NULL = noch nicht typisiert).
        CheckConstraint(
            "kind IS NULL OR kind IN ('organization', 'person', 'collection')",
            name="ck_correspondents_kind",
        ),
        # Zwei-Ebenen-Regel: nur Personen dürfen einer Organisation zugeordnet sein.
        # Dass der Parent selbst eine Organisation ist, erzwingt die Service-Schicht
        # (Cross-Row-Bedingung, per CHECK nicht ausdrückbar).
        CheckConstraint(
            "parent_id IS NULL OR kind = 'person'",
            name="ck_correspondents_parent_only_person",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'organization' | 'person' | 'collection'; NULL = noch nicht typisiert.
    kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Zugehörige Organisation einer Person (Self-FK, genau zwei Ebenen).
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("correspondents.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    parent: Mapped["Correspondent | None"] = relationship(
        "Correspondent",
        remote_side=[id],
        backref="children",
        lazy="selectin",
    )

    @property
    def parent_name(self) -> str | None:
        """Name der zugehörigen Organisation (für die Serialisierung)."""
        return self.parent.name if self.parent is not None else None

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
    """Alternative Schreibweise bzw. Erkennungsname für die Auflösung."""

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
