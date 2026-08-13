"""manual document connections for dossier notes and links.

Revision ID: 070_dossier_item_connections
Revises: 069_dossier_favorite
Create Date: 2026-08-11 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "070_dossier_item_connections"
down_revision: Union[str, None] = "069_dossier_favorite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dossier_items",
        sa.Column("attached_to_item_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_dossier_items_attached_to_item_id",
        "dossier_items",
        "dossier_items",
        ["attached_to_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_dossier_items_attached_to_item_id",
        "dossier_items",
        ["attached_to_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dossier_items_attached_to_item_id", table_name="dossier_items")
    op.drop_constraint(
        "fk_dossier_items_attached_to_item_id",
        "dossier_items",
        type_="foreignkey",
    )
    op.drop_column("dossier_items", "attached_to_item_id")
