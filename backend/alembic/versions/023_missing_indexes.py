"""add missing indexes for sort and lookup columns

Revision ID: 023_missing_indexes
Revises: 022_settings_ai_ocr_quality
Create Date: 2026-05-24 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023_missing_indexes"
down_revision: Union[str, None] = "022_settings_ai_ocr_quality"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # documents.updated_at — used as default sort column in list_documents()
    op.create_index("ix_documents_updated_at", "documents", ["updated_at"], unique=False)

    # documents.is_unread — partial index; only indexes the true rows (small, fast)
    op.create_index(
        "ix_documents_is_unread",
        "documents",
        ["is_unread"],
        unique=False,
        postgresql_where=sa.text("is_unread = true"),
    )

    # documents.file_sha256 — used in dedup lookup _find_existing_document_by_sha256()
    op.create_index("ix_documents_file_sha256", "documents", ["file_sha256"], unique=False)

    # tags.lower(name) — functional index for case-insensitive tag name lookups
    op.execute("CREATE INDEX ix_tags_name_lower ON tags (lower(name))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tags_name_lower")
    op.drop_index("ix_documents_file_sha256", table_name="documents")
    op.drop_index("ix_documents_is_unread", table_name="documents")
    op.drop_index("ix_documents_updated_at", table_name="documents")
