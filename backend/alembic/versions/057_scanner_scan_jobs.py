"""scanner scan job lifecycle.

Revision ID: 057_scanner_scan_jobs
Revises: 056_scanner_scan_commands
Create Date: 2026-06-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "057_scanner_scan_jobs"
down_revision: Union[str, None] = "056_scanner_scan_commands"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scanner_scan_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scanner_device_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scanner_devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "import_inbox_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("import_inbox_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_file_id", UUID(as_uuid=True), nullable=True),
        sa.Column("command", sa.Text(), nullable=False, server_default="hardware"),
        sa.Column("state", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_scanner_scan_jobs_device_state",
        "scanner_scan_jobs",
        ["scanner_device_id", "state"],
    )
    op.create_index(
        "ix_scanner_scan_jobs_import_inbox_item_id",
        "scanner_scan_jobs",
        ["import_inbox_item_id"],
    )
    op.create_index(
        "ix_scanner_scan_jobs_created_at",
        "scanner_scan_jobs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_scanner_scan_jobs_created_at", table_name="scanner_scan_jobs")
    op.drop_index("ix_scanner_scan_jobs_import_inbox_item_id", table_name="scanner_scan_jobs")
    op.drop_index("ix_scanner_scan_jobs_device_state", table_name="scanner_scan_jobs")
    op.drop_table("scanner_scan_jobs")
