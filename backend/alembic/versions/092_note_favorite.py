"""Notizen favorisieren: is_favorite-Spalte.

Notizen bekommen – wie Dokumente – ein echtes Favoriten-Flag (eigene boolesche
Spalte, nicht als JSONB-Attribut), damit „Favoriten" im schlanken Listeneintrag
verfügbar, serverseitig sortierbar und in den globalen Favoriten-Bereich
integrierbar ist. Partieller Index nur über die favorisierten Zeilen.

Revision ID: 092_note_favorite
Revises: 091_note_notebook
Create Date: 2026-09-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "092_note_favorite"
down_revision: Union[str, None] = "091_note_notebook"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "note",
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_note_owner_favorite",
        "note",
        ["owner_id"],
        postgresql_where=sa.text("is_favorite"),
    )


def downgrade() -> None:
    op.drop_index("ix_note_owner_favorite", table_name="note")
    op.drop_column("note", "is_favorite")
