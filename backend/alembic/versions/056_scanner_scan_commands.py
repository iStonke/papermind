"""scanner scan command queue (UI-triggered scans).

Revision ID: 056_scanner_scan_commands
Revises: 055_scanner_scanning_status
Create Date: 2026-06-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "056_scanner_scan_commands"
down_revision: Union[str, None] = "055_scanner_scanning_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scanner_scan_commands",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scanner_device_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scanner_devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column(
            "requested_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_scanner_scan_commands_pending",
        "scanner_scan_commands",
        ["scanner_device_id", "consumed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_scanner_scan_commands_pending", table_name="scanner_scan_commands")
    op.drop_table("scanner_scan_commands")
