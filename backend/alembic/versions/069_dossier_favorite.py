"""favorite flag for dossiers (light tables).

Revision ID: 069_dossier_favorite
Revises: 068_dossier_board_positions
Create Date: 2026-08-09 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "069_dossier_favorite"
down_revision: Union[str, None] = "068_dossier_board_positions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dossiers",
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_dossiers_owner_favorite",
        "dossiers",
        ["owner_id", "is_favorite"],
        postgresql_where=sa.text("is_favorite"),
    )


def downgrade() -> None:
    op.drop_index("ix_dossiers_owner_favorite", table_name="dossiers")
    op.drop_column("dossiers", "is_favorite")
