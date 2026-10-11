"""Notiz-Favoriten entfernen: is_favorite-Spalte + Teilindex löschen.

Notizen kennen nur noch Pins (``pinned_at``, Migration 111). Der Favoriten-Stern
ist aus Notizliste, Verwaltung und globalem Favoriten-Bereich verschwunden; die
Spalte aus 092 wird damit nicht mehr gelesen oder geschrieben. Noch favorisierte
Notizen werden vorher angepinnt. Das Downgrade stellt Spalte und Index leer
(alle ``false``) wieder her; die Pins bleiben bestehen.

Revision ID: 113_drop_note_favorite
Revises: 112_chunk_search_vector
Create Date: 2026-10-11 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "113_drop_note_favorite"
down_revision: Union[str, None] = "112_chunk_search_vector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Noch favorisierte Notizen gehen nicht verloren: sie werden angepinnt (wie in
    # 111, dort für die damaligen Favoriten). Bestehende Pins bleiben unverändert.
    op.execute(
        "UPDATE note SET pinned_at = updated_at "
        "WHERE is_favorite AND pinned_at IS NULL AND NOT is_template"
    )
    op.drop_index("ix_note_owner_favorite", table_name="note", if_exists=True)
    op.drop_column("note", "is_favorite")


def downgrade() -> None:
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
