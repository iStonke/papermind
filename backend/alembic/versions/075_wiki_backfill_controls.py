"""add safe controls and canary limits to wiki backfills.

Revision ID: 075_wiki_backfill_controls
Revises: 074_wiki_scalable_backfill
Create Date: 2026-08-12 04:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "075_wiki_backfill_controls"
down_revision: Union[str, None] = "074_wiki_scalable_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_wiki_backfill_runs_owner_active", table_name="wiki_backfill_runs")
    op.drop_constraint("ck_wiki_backfill_runs_status", "wiki_backfill_runs", type_="check")
    op.create_check_constraint(
        "ck_wiki_backfill_runs_status",
        "wiki_backfill_runs",
        "status IN ('queued', 'running', 'paused', 'done', 'failed', 'cancelled')",
    )
    op.add_column("wiki_backfill_runs", sa.Column("document_limit", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_wiki_backfill_runs_document_limit",
        "wiki_backfill_runs",
        "document_limit IS NULL OR (document_limit >= 1 AND document_limit <= 5000)",
    )
    op.create_index(
        "uq_wiki_backfill_runs_owner_active",
        "wiki_backfill_runs",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'paused')"),
    )


def downgrade() -> None:
    op.drop_index("uq_wiki_backfill_runs_owner_active", table_name="wiki_backfill_runs")
    op.drop_constraint("ck_wiki_backfill_runs_document_limit", "wiki_backfill_runs", type_="check")
    op.drop_column("wiki_backfill_runs", "document_limit")
    op.drop_constraint("ck_wiki_backfill_runs_status", "wiki_backfill_runs", type_="check")
    op.execute("UPDATE wiki_backfill_runs SET status = 'queued' WHERE status = 'paused'")
    op.execute("UPDATE wiki_backfill_runs SET status = 'failed' WHERE status = 'cancelled'")
    op.create_check_constraint(
        "ck_wiki_backfill_runs_status",
        "wiki_backfill_runs",
        "status IN ('queued', 'running', 'done', 'failed')",
    )
    op.create_index(
        "uq_wiki_backfill_runs_owner_active",
        "wiki_backfill_runs",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
