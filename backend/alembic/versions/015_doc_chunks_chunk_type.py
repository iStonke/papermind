"""add chunk_type to doc_chunks

Revision ID: 015_doc_chunks_chunk_type
Revises: 014_jobs_add_tag_type
Create Date: 2026-02-28 00:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "015_doc_chunks_chunk_type"
down_revision: Union[str, None] = "014_jobs_add_tag_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "doc_chunks",
        sa.Column("chunk_type", sa.String(length=32), nullable=False, server_default=sa.text("'header'")),
    )
    op.create_index("ix_doc_chunks_chunk_type", "doc_chunks", ["chunk_type"], unique=False)
    op.create_check_constraint(
        "ck_doc_chunks_chunk_type",
        "doc_chunks",
        "chunk_type IN ('header', 'invoice_table', 'invoice_total')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_doc_chunks_chunk_type", "doc_chunks", type_="check")
    op.drop_index("ix_doc_chunks_chunk_type", table_name="doc_chunks")
    op.drop_column("doc_chunks", "chunk_type")
