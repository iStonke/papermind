import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ImportInboxItem(Base):
    __tablename__ = "import_inbox_items"
    __table_args__ = (
        Index("ix_import_inbox_items_owner_id", "owner_id"),
        Index("ix_import_inbox_items_scanner_device_id", "scanner_device_id"),
        Index("ix_import_inbox_items_source_type", "source_type"),
        Index("ix_import_inbox_items_claimed_at", "claimed_at"),
        Index("ix_import_inbox_items_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    scanner_device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scanner_devices.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="shortcut")
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    client_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
