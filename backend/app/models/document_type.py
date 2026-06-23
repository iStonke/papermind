import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentType(Base):
    """Verwaltbares Vokabular der zur Verfügung stehenden Dokumenttypen.

    Dokumente speichern ihren Dokumenttyp als Namen (denormalisiert, siehe
    ``Document.document_type``). Diese Tabelle ist die zentrale, in den
    Einstellungen pflegbare Liste der auswählbaren Dokumenttypen.
    """

    __tablename__ = "document_types"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_document_types_owner_name"),
        Index("ix_document_types_owner_name", "owner_id", "name"),
        CheckConstraint(
            "area IS NULL OR area IN "
            "('finance', 'contracts_law', 'insurance', 'government_tax', "
            "'employment', 'health', 'access_it', 'other')",
            name="ck_document_types_area",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    naming_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    area: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
