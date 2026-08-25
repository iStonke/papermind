from sqlalchemy import Column, DateTime, ForeignKey, Index, Table, func
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


# Verknüpfung Notiz ↔ Tag auf derselben ``tags``-Tabelle wie Dokumente
# (gemeinsames Vokabular). Reine Assoziationstabelle, RLS über die Notiz.
note_tags = Table(
    "note_tags",
    Base.metadata,
    Column("note_id", UUID(as_uuid=True), ForeignKey("note.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Index("ix_note_tags_note_id", "note_id"),
    Index("ix_note_tags_tag_id", "tag_id"),
)
