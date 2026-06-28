import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScannerDevice(Base):
    __tablename__ = "scanner_devices"
    __table_args__ = (
        UniqueConstraint("device_key", name="uq_scanner_devices_device_key"),
        Index("ix_scanner_devices_enabled", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    live_page_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scanning_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScannerScanCommand(Base):
    """Befehls-Queue für UI-ausgelöste Scans (Container → Host).

    Der Web-Container kann den Scanner nicht direkt ansprechen (USB hängt am
    Host, Container unprivilegiert). Stattdessen reiht der API-Endpoint einen
    Befehl hier ein; der Worker drained die Queue in seinem Sync-Tick und
    schreibt je Befehl eine Datei in scan-inbox, die der Host-Poller ausführt.
    Eine FIFO-Tabelle (statt einer einzelnen Spalte), damit schnelle
    "page, page, finish"-Folgen keine Seite verschlucken.
    """

    __tablename__ = "scanner_scan_commands"
    __table_args__ = (
        Index("ix_scanner_scan_commands_pending", "scanner_device_id", "consumed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scanner_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scanner_devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    command: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScannerDeviceRecipient(Base):
    __tablename__ = "scanner_device_recipients"
    __table_args__ = (
        UniqueConstraint("scanner_device_id", "user_id", name="uq_scanner_device_recipients_device_user"),
        Index("ix_scanner_device_recipients_user_id", "user_id"),
    )

    scanner_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scanner_devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
