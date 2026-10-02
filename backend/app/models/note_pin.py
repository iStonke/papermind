"""Plain-text thoughts, separate from editor notes; tags share the existing vocabulary."""
import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

note_pin_tags = Table(
    "note_pin_tags", Base.metadata,
    Column("pin_id", UUID(as_uuid=True), ForeignKey("note_pin.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

class NotePin(Base):
    __tablename__ = "note_pin"
    __table_args__ = (
        CheckConstraint("(position_x IS NULL AND position_y IS NULL) OR (position_x IS NOT NULL AND position_y IS NOT NULL AND position_x BETWEEN 0 AND 100000 AND position_y BETWEEN 0 AND 100000)", name="ck_note_pin_position"),
        CheckConstraint("status IN ('open', 'sorted', 'archived')", name="ck_note_pin_status"),
        CheckConstraint("length(trim(text)) > 0 AND length(text) <= 20000", name="ck_note_pin_text"),
        Index("ix_note_pin_owner_collection_created", "owner_id", "collection_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    collection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("note_collection.id", ondelete="RESTRICT"), nullable=False)
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("thought_room.id", ondelete="RESTRICT"), nullable=True)
    title_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position_x: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_y: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    tags: Mapped[list["Tag"]] = relationship("Tag", secondary=note_pin_tags, lazy="selectin")

class ThoughtRoom(Base):
    __tablename__ = "thought_room"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    collection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("note_collection.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
