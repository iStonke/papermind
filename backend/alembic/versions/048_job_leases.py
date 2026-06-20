"""add worker leases to background jobs

Revision ID: 048_job_leases
Revises: 047_user_session_version
Create Date: 2026-06-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "048_job_leases"
down_revision: Union[str, None] = "047_user_session_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("worker_id", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("lease_token", UUID(as_uuid=True), nullable=True))
    op.add_column("jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_jobs_running_lease_expires",
        "jobs",
        ["lease_expires_at"],
        unique=False,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_running_lease_expires", table_name="jobs")
    op.drop_column("jobs", "lease_expires_at")
    op.drop_column("jobs", "heartbeat_at")
    op.drop_column("jobs", "lease_token")
    op.drop_column("jobs", "worker_id")
