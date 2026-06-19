"""add owner-scoped indexes for active document lists

Revision ID: 046_document_list_indexes
Revises: 045_import_inbox_owner_rls
Create Date: 2026-06-19 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "046_document_list_indexes"
down_revision: Union[str, None] = "045_import_inbox_owner_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive only: no document rows or existing indexes are modified.
    op.create_index(
        "ix_documents_owner_active_created",
        "documents",
        ["owner_id", "created_at", "id"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "ix_documents_owner_active_document_date",
        "documents",
        ["owner_id", "document_date", "created_at"],
        unique=False,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_owner_active_document_date", table_name="documents")
    op.drop_index("ix_documents_owner_active_created", table_name="documents")
