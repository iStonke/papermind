"""scanner live page mode flag.

Revision ID: 054_scanner_live_page_mode
Revises: 053_scanner_import_inbox
Create Date: 2026-06-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "054_scanner_live_page_mode"
down_revision: Union[str, None] = "053_scanner_import_inbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scanner_devices",
        sa.Column("live_page_mode", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("scanner_devices", "live_page_mode")
