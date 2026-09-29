import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LearnCourse(Base):
    """Kurs – Container pro Modul im Lernbereich (z. B. „Computergrafik 1").

    Oberste, owner-scoped Ebene: bündelt Sitzungen und Lernblätter. Trägt den
    Default-Artefakttyp (Vorbelegung bei der Nachbereitung) und ein Flag, ob ein
    brauchbares Skript vorliegt (steuert später die skript-gestützte KI).

    Reine Sicht-/Verknüpfungsebene – der eigentliche Stoff bleibt in Notizen und
    Dokumenten. Siehe docs/design/lernbereich-datenmodell.md §3.1.
    """

    __tablename__ = "learn_course"
    __table_args__ = (
        Index("ix_learn_course_owner", "owner_id", "position", "title"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    module_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_artifact_type: Mapped[str] = mapped_column(String(24), nullable=False, server_default="fakt")
    has_script: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearnSession(Base):
    """Sitzung – eine Vorlesung/ein Termin innerhalb eines Kurses.

    Verweist auf genau eine Mitschrift-Notiz (``note_id``, SET NULL) und ordnet
    die zugehörigen Lernblätter. Siehe Datenmodell §3.3.
    """

    __tablename__ = "learn_session"
    __table_args__ = (
        Index("ix_learn_session_course", "course_id", "ordinal"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learn_course.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    session_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Genau eine Mitschrift-Notiz; SET NULL, falls die Notiz gelöscht wird.
    note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("note.id", ondelete="SET NULL"), nullable=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearnSheet(Base):
    """Lernblatt – verdichtete, lernbare Sicht aus markierten Inhalten.

    Pro Sitzung oder themenübergreifend. Enthält später die Artefakte als
    Referenzen; hier lebt die reine Lern-Struktur (Reihenfolge/Gruppierung im
    ``structure``-JSON) plus Status und Favorit für die Leuchttisch-Ansicht.
    Siehe Datenmodell §3.8.
    """

    __tablename__ = "learn_sheet"
    __table_args__ = (
        Index("ix_learn_sheet_course", "course_id", "position"),
        Index("ix_learn_sheet_session", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learn_course.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learn_session.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # session | topic – ob das Blatt zu einer Sitzung oder themenübergreifend gehört.
    scope: Mapped[str] = mapped_column(String(12), nullable=False, server_default="session")
    # draft | in_progress | worked | archived
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Legitimer Eigen-Content: Gruppen + Reihenfolge + Überblickssätze (§2.1).
    structure: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Menschenlesbarer Quellhinweis (später aus verknüpfter Notiz/Folie abgeleitet).
    source_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearnCard(Base):
    """Lernkarte (Artefakt) innerhalb eines Lernblatts.

    Vereinfachte Fassung der Artefakt-Ebene aus dem Datenmodell (§3.6): trägt den
    Lerntyp (Bloom-orientiert), Vorderseite (Frage/Aufgabe) und – wo sinnvoll –
    Rückseite (Antwort/Lösung). Anker/Herkunft/Prüf-Status folgen später mit der
    Notiz-Marker-Anbindung.
    """

    __tablename__ = "learn_card"
    __table_args__ = (
        Index("ix_learn_card_sheet", "sheet_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learn_sheet.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # fakt | prozess | zusammenhang | prozedural | verstaendnis | uebung
    kind: Mapped[str] = mapped_column(String(24), nullable=False, server_default="fakt")
    front: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    back: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Lernstand aus dem Lernmodus: open (noch offen) | weak (nicht gekonnt) |
    # medium (mit Mühe) | strong (sicher). Speist die Lernstand-Balken.
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="open")
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Herkunft: markierte Notizzeile (stabile pmId). Gesetzt, wenn die Karte aus
    # einer Nachbereitung entstand; NULL bei manuell angelegten Karten.
    source_note_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("note.id", ondelete="SET NULL"), nullable=True
    )
    source_pm_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearnRun(Base):
    """Gespeicherter Durchlauf im Lernmodus.

    Hält bewusst nur die Zusammenfassung eines Durchlaufs. Der aktuelle
    Lernstand jeder einzelnen Karte bleibt weiterhin auf ``LearnCard``.
    """

    __tablename__ = "learn_run"
    __table_args__ = (
        Index("ix_learn_run_course_started", "course_id", "started_at"),
        Index("ix_learn_run_sheet", "sheet_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learn_course.id", ondelete="CASCADE"), nullable=False
    )
    sheet_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("learn_sheet.id", ondelete="SET NULL"), nullable=True
    )
    scope: Mapped[str] = mapped_column(String(12), nullable=False, server_default="sheet")
    total_cards: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    assessed_cards: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    weak_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    medium_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    strong_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LearnMarker(Base):
    """Lern-Marker – Projektion aus dem Notiz-JSON (wie note_task).

    Eine als lernrelevant markierte Notizzeile (`attrs.learn` + stabile
    `attrs.pmId`). Wird bei jedem Notiz-Save neu berechnet; die Wahrheit bleibt
    die Notiz. Grundlage der Nachbereitung: „offene" Marker sind solche, aus
    denen noch keine Karte entstanden ist (kein learn_card mit passendem
    source_pm_id). Siehe docs/design/lernbereich-datenmodell.md §3.4.
    """

    __tablename__ = "learn_marker"
    __table_args__ = (
        UniqueConstraint("note_id", "node_pm_id", name="uq_learn_marker_note_node"),
        Index("ix_learn_marker_owner", "owner_id"),
        Index("ix_learn_marker_note", "note_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("note.id", ondelete="CASCADE"), nullable=False
    )
    node_pm_id: Mapped[str] = mapped_column(String(16), nullable=False)
    # lernen (generisch) | fakt | warum | aufgabe | analyse | …
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="lernen")
    snippet: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    context: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
