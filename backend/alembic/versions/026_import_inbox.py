"""add import inbox items

Revision ID: 026_import_inbox
Revises: 025_settings_trash_retention
Create Date: 2026-05-25
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "026_import_inbox"
down_revision: Union[str, None] = "025_settings_trash_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_inbox_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_file_id"),
    )
    op.create_index("ix_import_inbox_items_claimed_at", "import_inbox_items", ["claimed_at"], unique=False)
    op.create_index("ix_import_inbox_items_created_at", "import_inbox_items", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_import_inbox_items_created_at", table_name="import_inbox_items")
    op.drop_index("ix_import_inbox_items_claimed_at", table_name="import_inbox_items")
    op.drop_table("import_inbox_items")
