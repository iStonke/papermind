"""add backup_runs table

Revision ID: 036_backup_runs
Revises: 035_naming_templates_house_style
Create Date: 2026-06-04 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "036_backup_runs"
down_revision: Union[str, None] = "035_naming_templates_house_style"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backup_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default="running", nullable=False),
        sa.Column("kind", sa.Text(), server_default="manual", nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('running', 'success', 'failed')", name="ck_backup_runs_status"),
        sa.CheckConstraint("kind IN ('scheduled', 'manual')", name="ck_backup_runs_kind"),
    )
    op.create_index("ix_backup_runs_started_at", "backup_runs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_backup_runs_started_at", table_name="backup_runs")
    op.drop_table("backup_runs")
