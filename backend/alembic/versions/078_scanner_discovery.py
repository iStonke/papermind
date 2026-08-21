"""scanner discovery and setup state.

Revision ID: 078_scanner_discovery
Revises: 077_dossier_image_items
Create Date: 2026-08-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "078_scanner_discovery"
down_revision: Union[str, None] = "077_dossier_image_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scanner_devices", sa.Column("connection_uri", sa.Text(), nullable=True))
    op.add_column("scanner_devices", sa.Column("hardware_name", sa.Text(), nullable=True))
    op.add_column(
        "scanner_devices",
        sa.Column("configured", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column("scanner_devices", sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_scanner_devices_connection_uri",
        "scanner_devices",
        ["connection_uri"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_scanner_devices_connection_uri", "scanner_devices", type_="unique")
    op.drop_column("scanner_devices", "discovered_at")
    op.drop_column("scanner_devices", "configured")
    op.drop_column("scanner_devices", "hardware_name")
    op.drop_column("scanner_devices", "connection_uri")
