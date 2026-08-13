"""add resumable owner-scoped wiki backfill runs.

Revision ID: 074_wiki_scalable_backfill
Revises: 073_wiki_evidence_immutability
Create Date: 2026-08-12 02:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "074_wiki_scalable_backfill"
down_revision: Union[str, None] = "073_wiki_evidence_immutability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "wiki_backfill_runs",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("cursor_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("total_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_proposals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_documents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("lease_token", UUID(as_uuid=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="ck_wiki_backfill_runs_status"),
        sa.CheckConstraint("batch_size >= 1 AND batch_size <= 50", name="ck_wiki_backfill_runs_batch_size"),
        sa.CheckConstraint(
            "total_documents >= 0 AND processed_documents >= 0 AND updated_documents >= 0 "
            "AND review_proposals >= 0 AND failed_documents >= 0",
            name="ck_wiki_backfill_runs_counts",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wiki_backfill_runs_owner_id", "wiki_backfill_runs", ["owner_id"])
    op.create_index("ix_wiki_backfill_runs_owner_created", "wiki_backfill_runs", ["owner_id", "created_at"])
    op.create_index(
        "uq_wiki_backfill_runs_owner_active",
        "wiki_backfill_runs",
        ["owner_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.execute("ALTER TABLE wiki_backfill_runs ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY wiki_backfill_runs_owner_isolation ON wiki_backfill_runs "
        f"USING (owner_id = {_OWNER_EXPR}) WITH CHECK (owner_id = {_OWNER_EXPR})"
    )
    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON wiki_backfill_runs TO "{role}";
              END IF;
            END $$;
            """
        )
    op.execute(
        "CREATE TRIGGER backup_source_dirty_wiki_backfill_runs "
        "AFTER INSERT OR UPDATE OR DELETE ON wiki_backfill_runs "
        "FOR EACH STATEMENT EXECUTE FUNCTION mark_backup_source_dirty()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER backup_source_dirty_wiki_backfill_runs ON wiki_backfill_runs")
    op.execute("DROP POLICY wiki_backfill_runs_owner_isolation ON wiki_backfill_runs")
    op.drop_index("uq_wiki_backfill_runs_owner_active", table_name="wiki_backfill_runs")
    op.drop_index("ix_wiki_backfill_runs_owner_created", table_name="wiki_backfill_runs")
    op.drop_index("ix_wiki_backfill_runs_owner_id", table_name="wiki_backfill_runs")
    op.drop_table("wiki_backfill_runs")
