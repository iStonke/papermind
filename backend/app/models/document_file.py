import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DocumentFile(Base):
    __tablename__ = "document_files"
    __table_args__ = (
        CheckConstraint(
            "role IN ('original', 'ocr', 'preview_pdf', 'thumbnail')",
            name="ck_document_files_role",
        ),
        UniqueConstraint("document_id", "role", name="uq_document_files_document_role"),
        Index("ix_document_files_document_id", "document_id"),
        Index("ix_document_files_role", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    file_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    document: Mapped["Document"] = relationship("Document", back_populates="files", lazy="select")
