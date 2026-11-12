import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, case, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
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
        # Hierarchie Sammlung → Organisation → Person: Sammlungen und Einträge
        # ohne Typ gehören zu niemandem. Welche Eltern erlaubt sind, erzwingt
        # die Service-Schicht (Cross-Row-Bedingung, per CHECK nicht ausdrückbar).
        CheckConstraint(
            "parent_id IS NULL OR kind IN ('person', 'organization')",
            name="ck_correspondents_parent_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'organization' | 'person' | 'collection'; NULL = noch nicht typisiert.
    kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Übergeordneter Eintrag: Organisation/Sammlung einer Person, Sammlung
    # einer Organisation (Self-FK, höchstens drei Ebenen).
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

    @hybrid_property
    def display_short_name(self) -> str | None:
        if self.kind == "collection":
            return None
        return (self.short_name or "").strip() or None

    @display_short_name.inplace.expression
    @classmethod
    def _display_short_name_expression(cls):
        return case((cls.kind.is_distinct_from("collection"), func.nullif(func.trim(cls.short_name), "")))

    @property
    def parent_short_name(self) -> str | None:
        return self.parent.display_short_name if self.parent is not None else None

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


class CorrespondentRelation(Base):
    """Seitliche Verbindung zweier Korrespondenten (neben „gehört zu“).

    ``successor``: source wurde zu target (Umbenennung, Fusion) – source ist
    der Vorgänger. ``acts_for``: source handelt im Auftrag von target
    (Hausverwaltung → Eigentümer, Inkasso → Gläubiger).
    """

    __tablename__ = "correspondent_relations"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "kind", name="uq_correspondent_relations_pair"),
        CheckConstraint("kind IN ('successor', 'acts_for')", name="ck_correspondent_relations_kind"),
        CheckConstraint("source_id <> target_id", name="ck_correspondent_relations_distinct"),
        # Ein Vorgänger geht in genau einem Nachfolger auf.
        Index(
            "uq_correspondent_relations_single_successor",
            "source_id",
            unique=True,
            postgresql_where=text("kind = 'successor'"),
        ),
        Index("ix_correspondent_relations_target_id", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("correspondents.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("correspondents.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
