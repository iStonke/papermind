"""split document date fields and migrate doc_date to document_date

Revision ID: 017_document_date_ssot
Revises: 016_chunk_type_bank
Create Date: 2026-02-28 10:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "017_document_date_ssot"
down_revision: Union[str, None] = "016_chunk_type_bank"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE documents SET created_at = COALESCE(created_at, now())")

    op.alter_column(
        "documents",
        "doc_date",
        new_column_name="document_date",
        existing_type=sa.Date(),
        existing_nullable=True,
    )

    op.add_column(
        "documents",
        sa.Column("document_date_source", sa.String(length=16), nullable=False, server_default="manual"),
    )
    op.add_column("documents", sa.Column("document_date_confidence", sa.Float(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("document_date_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.execute("UPDATE documents SET document_date_source = 'manual' WHERE document_date_source IS NULL")
    op.execute("UPDATE documents SET document_date_confidence = NULL WHERE document_date_source <> 'ocr'")

    op.drop_index("ix_documents_doc_date", table_name="documents")
    op.create_index("ix_documents_document_date", "documents", ["document_date"], unique=False)

    op.create_check_constraint(
        "ck_documents_document_date_source",
        "documents",
        "document_date_source IN ('manual', 'ocr', 'pdf_meta')",
    )
    op.create_check_constraint(
        "ck_documents_document_date_confidence",
        "documents",
        "document_date_confidence IS NULL OR (document_date_confidence >= 0 AND document_date_confidence <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_document_date_confidence", "documents", type_="check")
    op.drop_constraint("ck_documents_document_date_source", "documents", type_="check")

    op.drop_index("ix_documents_document_date", table_name="documents")

    op.drop_column("documents", "document_date_candidates")
    op.drop_column("documents", "document_date_confidence")
    op.drop_column("documents", "document_date_source")

    op.alter_column(
        "documents",
        "document_date",
        new_column_name="doc_date",
        existing_type=sa.Date(),
        existing_nullable=True,
    )
    op.create_index("ix_documents_doc_date", "documents", ["doc_date"], unique=False)
