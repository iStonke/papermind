"""add saved searches for smart folders

Revision ID: 008_saved_searches
Revises: 007_text_source_embedded
Create Date: 2026-02-27 11:50:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008_saved_searches"
down_revision: Union[str, None] = "007_text_source_embedded"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("query_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_saved_searches"),
        sa.UniqueConstraint("name", name="uq_saved_searches_name"),
    )

    op.create_index("ix_saved_searches_name", "saved_searches", ["name"], unique=False)
    op.execute("CREATE UNIQUE INDEX uq_saved_searches_name_ci ON saved_searches (LOWER(name));")

    op.execute(
        """
        CREATE TRIGGER trg_saved_searches_updated_at
        BEFORE UPDATE ON saved_searches
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_saved_searches_updated_at ON saved_searches;")
    op.execute("DROP INDEX IF EXISTS uq_saved_searches_name_ci;")
    op.drop_index("ix_saved_searches_name", table_name="saved_searches")
    op.drop_table("saved_searches")
