"""Lernbereich – gespeicherte Lerndurchläufe.

Revision ID: 099_learn_runs
Revises: 098_learn_card_status
Create Date: 2026-09-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "099_learn_runs"
down_revision: Union[str, None] = "098_learn_card_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def _grant(table: str) -> None:
    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO "{role}";
              END IF;
            END $$;
            """
        )


def upgrade() -> None:
    op.create_table(
        "learn_run",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sheet_id", UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(length=12), nullable=False, server_default="sheet"),
        sa.Column("total_cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("assessed_cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("weak_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("medium_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("strong_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["learn_course.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sheet_id"], ["learn_sheet.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learn_run_owner", "learn_run", ["owner_id"])
    op.create_index("ix_learn_run_course_started", "learn_run", ["course_id", "started_at"])
    op.create_index("ix_learn_run_sheet", "learn_run", ["sheet_id"])

    owner_check = f"owner_id = {_OWNER_EXPR}"
    op.execute("ALTER TABLE learn_run ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY learn_run_owner_isolation ON learn_run "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("learn_run")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS learn_run_owner_isolation ON learn_run")
    op.drop_table("learn_run")
