"""scanner scanning status timestamp.

Revision ID: 055_scanner_scanning_status
Revises: 054_scanner_live_page_mode
Create Date: 2026-06-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "055_scanner_scanning_status"
down_revision: Union[str, None] = "054_scanner_live_page_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scanner_devices",
        sa.Column("scanning_since", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scanner_devices", "scanning_since")
