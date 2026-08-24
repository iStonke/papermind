"""Soft-delete fields for notes so they participate in the shared trash.

Revision ID: 082_note_trash
Revises: 081_notes
Create Date: 2026-08-24 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "082_note_trash"
down_revision: Union[str, None] = "081_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "note",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("note", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_note_owner_deleted_updated",
        "note",
        ["owner_id", "is_deleted", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_note_owner_deleted_updated", table_name="note")
    op.drop_column("note", "deleted_at")
    op.drop_column("note", "is_deleted")
