import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BIGINT, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.document_tag import document_tags


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('imported', 'processing', 'ready', 'failed')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "text_source IN ('none', 'embedded', 'ocr')",
            name="ck_documents_text_source",
        ),
        CheckConstraint(
            "ocr_status IN ('not_started', 'queued', 'running', 'done', 'failed')",
            name="ck_documents_ocr_status",
        ),
        CheckConstraint(
            "ocr_quality_status IS NULL OR ocr_quality_status IN ('good', 'warning', 'error')",
            name="ck_documents_ocr_quality_status",
        ),
        CheckConstraint(
            "ocr_confidence_score IS NULL OR (ocr_confidence_score >= 0 AND ocr_confidence_score <= 100)",
            name="ck_documents_ocr_confidence_score",
        ),
        CheckConstraint(
            "embedding_status IN ('not_started', 'queued', 'running', 'done', 'failed')",
            name="ck_documents_embedding_status",
        ),
        CheckConstraint(
            "ai_status IN ('pending', 'done', 'skipped', 'error')",
            name="ck_documents_ai_status",
        ),
        CheckConstraint(
            "ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)",
            name="ck_documents_ai_confidence",
        ),
        CheckConstraint(
            "duplicate_kind IS NULL OR duplicate_kind IN ('exact', 'text', 'image')",
            name="ck_documents_duplicate_kind",
        ),
        CheckConstraint(
            "document_date_source IN ('manual', 'ocr', 'pdf_meta')",
            name="ck_documents_document_date_source",
        ),
        CheckConstraint(
            "document_date_confidence IS NULL OR (document_date_confidence >= 0 AND document_date_confidence <= 1)",
            name="ck_documents_document_date_confidence",
        ),
        Index("ix_documents_created_at", "created_at"),
        Index("ix_documents_document_date", "document_date"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_document_type", "document_type"),
        Index("ix_documents_ocr_quality_status", "ocr_quality_status"),
        Index("ix_documents_embedding_status", "embedding_status"),
        Index("ix_documents_ai_status", "ai_status"),
        Index("ix_documents_ai_document_type", "ai_document_type"),
        Index("ix_documents_text_hash", "text_hash"),
        Index("ix_documents_duplicate_of_doc_id", "duplicate_of_doc_id"),
        Index("ix_documents_text_simhash64", "text_simhash64"),
        Index("ix_documents_first_page_phash64", "first_page_phash64"),
        Index("ix_documents_simhash_bucket1", "simhash_bucket1"),
        Index("ix_documents_simhash_bucket2", "simhash_bucket2"),
        Index("ix_documents_simhash_bucket3", "simhash_bucket3"),
        Index("ix_documents_simhash_bucket4", "simhash_bucket4"),
        Index("ix_documents_correspondent_id", "correspondent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_date_source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="manual")
    document_date_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    document_date_candidates: Mapped[dict[str, Any] | list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    correspondent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("correspondents.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="imported")
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text_hash_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text_simhash64: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    first_page_phash64: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    simhash_bucket1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    simhash_bucket2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    simhash_bucket3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    simhash_bucket4: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicate_of_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    duplicate_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duplicate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplicate_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    text_source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="none")
    ocr_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="not_started")
    ocr_quality_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ocr_confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_quality_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_processing_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="not_started")
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ai_sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    ai_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_suggested_tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    ai_processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_unread: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    is_deleted: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    @property
    def category(self) -> str | None:
        return self.document_type

    @category.setter
    def category(self, value: str | None) -> None:
        self.document_type = value

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_of_doc_id is not None

    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary=document_tags,
        back_populates="documents",
        lazy="selectin",
    )
    files: Mapped[list["DocumentFile"]] = relationship(
        "DocumentFile",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DocumentFile.created_at.desc()",
    )
    jobs: Mapped[list["Job"]] = relationship(
        "Job",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DocumentChunk.chunk_index.asc()",
    )
    annotations: Mapped[list["Annotation"]] = relationship(
        "Annotation",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select",
        foreign_keys="Annotation.document_id",
    )
