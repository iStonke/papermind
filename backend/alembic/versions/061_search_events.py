"""search events log for dashboard search statistics.

Revision ID: 061_search_events
Revises: 060_document_retention
Create Date: 2026-07-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "061_search_events"
down_revision: Union[str, None] = "060_document_retention"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "search_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_events_owner_id", "search_events", ["owner_id"])
    op.create_index("ix_search_events_owner_created", "search_events", ["owner_id", "created_at"])
    op.create_index("ix_search_events_owner_term", "search_events", ["owner_id", "term"])

    cond = f"owner_id = {_OWNER_EXPR}"
    op.execute("ALTER TABLE search_events ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS search_events_owner_isolation ON search_events")
    op.execute(
        f"CREATE POLICY search_events_owner_isolation ON search_events "
        f"USING ({cond}) WITH CHECK ({cond})"
    )

    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON search_events TO "{role}";
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS search_events_owner_isolation ON search_events")
    op.drop_index("ix_search_events_owner_term", table_name="search_events")
    op.drop_index("ix_search_events_owner_created", table_name="search_events")
    op.drop_index("ix_search_events_owner_id", table_name="search_events")
    op.drop_table("search_events")
