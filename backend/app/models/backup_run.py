import uuid
from datetime import datetime

from sqlalchemy import BIGINT, DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BackupRun(Base):
    """Historie der Backup-Läufe (für Status/Details in den Einstellungen)."""

    __tablename__ = "backup_runs"
    __table_args__ = (Index("ix_backup_runs_started_at", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 'running' | 'success' | 'failed'
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="running")
    # 'scheduled' | 'manual'
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="manual")
    size_bytes: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
