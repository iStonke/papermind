import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentRetention(Base):
    __tablename__ = "document_retention"
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_evaluated', 'suggested', 'accepted', 'manual')",
            name="ck_document_retention_status",
        ),
        CheckConstraint(
            "paper_original IN ('unclear', 'keep', 'scan_sufficient', 'not_applicable')",
            name="ck_document_retention_paper_original",
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="not_evaluated")
    # None = unklar, -1 = unbegrenzt, 0+ = Jahre ab Dokumentdatum
    period_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retain_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    paper_original: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unclear")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
