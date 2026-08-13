"""free-canvas positions for dossier groups and items.

Adds nullable pos_x/pos_y coordinates so the light table can persist a free
2D layout. NULL means "not yet placed" — the frontend auto-arranges such rows
and writes coordinates back on the first drag.

Revision ID: 068_dossier_board_positions
Revises: 067_dossier_light_table
Create Date: 2026-08-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "068_dossier_board_positions"
down_revision: Union[str, None] = "067_dossier_light_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dossier_groups", sa.Column("pos_x", sa.Float(), nullable=True))
    op.add_column("dossier_groups", sa.Column("pos_y", sa.Float(), nullable=True))
    op.add_column("dossier_items", sa.Column("pos_x", sa.Float(), nullable=True))
    op.add_column("dossier_items", sa.Column("pos_y", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("dossier_items", "pos_y")
    op.drop_column("dossier_items", "pos_x")
    op.drop_column("dossier_groups", "pos_y")
    op.drop_column("dossier_groups", "pos_x")
