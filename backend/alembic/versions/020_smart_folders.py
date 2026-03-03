"""add smart folders with rule-based query json

Revision ID: 020_smart_folders
Revises: 019_orphan_tag_trigger
Create Date: 2026-03-01 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "020_smart_folders"
down_revision: Union[str, None] = "019_orphan_tag_trigger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "smart_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("query_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_smart_folders"),
        sa.UniqueConstraint("name", name="uq_smart_folders_name"),
    )
    op.create_index("ix_smart_folders_name", "smart_folders", ["name"], unique=False)
    op.execute("CREATE UNIQUE INDEX uq_smart_folders_name_ci ON smart_folders (LOWER(name));")
    op.execute(
        """
        CREATE TRIGGER trg_smart_folders_updated_at
        BEFORE UPDATE ON smart_folders
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_smart_folders_updated_at ON smart_folders;")
    op.execute("DROP INDEX IF EXISTS uq_smart_folders_name_ci;")
    op.drop_index("ix_smart_folders_name", table_name="smart_folders")
    op.drop_table("smart_folders")
