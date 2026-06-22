"""server-side sessions, persistent login limits and active-job uniqueness

Revision ID: 049_auth_sessions_jobs
Revises: 048_job_leases
Create Date: 2026-06-22 00:00:00.000000
"""

import os
from typing import Sequence, Union
from urllib.parse import unquote, urlsplit

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "049_auth_sessions_jobs"
down_revision: Union[str, None] = "048_job_leases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _app_role() -> str | None:
    raw = os.environ.get("APP_DATABASE_URL", "").strip()
    if not raw:
        return None
    return unquote(urlsplit(raw).username or "") or None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_user_active",
        "auth_sessions",
        ["user_id", "revoked_at", "expires_at"],
    )

    op.create_table(
        "auth_rate_limits",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    role = _app_role()
    if role:
        role_q = '"' + role.replace('"', '""') + '"'
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON auth_sessions TO {role_q}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON auth_rate_limits TO {role_q}")

    # Keep the oldest active job and make any historical duplicates terminal
    # before replacing the OCR-only constraint with a generic one.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY document_id, type
                       ORDER BY created_at ASC, id ASC
                   ) AS position
            FROM jobs
            WHERE status IN ('queued', 'running')
        )
        UPDATE jobs
        SET status = 'failed',
            error_message = COALESCE(error_message, 'Duplicate active job removed during migration'),
            finished_at = COALESCE(finished_at, now()),
            updated_at = now(),
            worker_id = NULL,
            lease_token = NULL,
            heartbeat_at = NULL,
            lease_expires_at = NULL
        FROM ranked
        WHERE jobs.id = ranked.id AND ranked.position > 1
        """
    )
    op.execute("DROP INDEX IF EXISTS uq_jobs_document_ocr_active")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_jobs_document_type_active
        ON jobs (document_id, type)
        WHERE status IN ('queued', 'running')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_jobs_document_type_active")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_jobs_document_ocr_active
        ON jobs (document_id)
        WHERE type = 'OCR' AND status IN ('queued', 'running')
        """
    )
    op.drop_table("auth_rate_limits")
    op.drop_index("ix_auth_sessions_user_active", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
