"""add document AI classification fields

Revision ID: 029_ai_classification_fields
Revises: 028_ocr_quality_fields
Create Date: 2026-05-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "029_ai_classification_fields"
down_revision: Union[str, None] = "028_ocr_quality_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ai_document_type", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("ai_document_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("ai_sender", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("ai_recipient", sa.String(length=255), nullable=True))
    op.add_column("documents", sa.Column("ai_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("documents", sa.Column("ai_currency", sa.String(length=8), nullable=True))
    op.add_column("documents", sa.Column("ai_summary", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("ai_suggested_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("documents", sa.Column("ai_confidence", sa.Float(), nullable=True))
    op.add_column("documents", sa.Column("ai_status", sa.String(length=16), server_default="pending", nullable=False))
    op.add_column("documents", sa.Column("ai_processed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_documents_ai_status",
        "documents",
        "ai_status IN ('pending', 'done', 'skipped', 'error')",
    )
    op.create_check_constraint(
        "ck_documents_ai_confidence",
        "documents",
        "ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)",
    )
    op.create_index("ix_documents_ai_status", "documents", ["ai_status"], unique=False)
    op.create_index("ix_documents_ai_document_type", "documents", ["ai_document_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_ai_document_type", table_name="documents")
    op.drop_index("ix_documents_ai_status", table_name="documents")
    op.drop_constraint("ck_documents_ai_confidence", "documents", type_="check")
    op.drop_constraint("ck_documents_ai_status", "documents", type_="check")
    op.drop_column("documents", "ai_processed_at")
    op.drop_column("documents", "ai_status")
    op.drop_column("documents", "ai_confidence")
    op.drop_column("documents", "ai_suggested_tags")
    op.drop_column("documents", "ai_summary")
    op.drop_column("documents", "ai_currency")
    op.drop_column("documents", "ai_amount")
    op.drop_column("documents", "ai_recipient")
    op.drop_column("documents", "ai_sender")
    op.drop_column("documents", "ai_document_date")
    op.drop_column("documents", "ai_document_type")
