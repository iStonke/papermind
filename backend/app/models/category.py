import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Category(Base):
    """Verwaltbares Vokabular der zur Verfügung stehenden Dokument-Kategorien.

    Dokumente speichern ihre Kategorie als Namen (denormalisiert, siehe
    ``Document.category``). Diese Tabelle ist die zentrale, in den Einstellungen
    pflegbare Liste der auswählbaren Kategorien.
    """

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("name", name="uq_categories_name"),
        Index("ix_categories_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
