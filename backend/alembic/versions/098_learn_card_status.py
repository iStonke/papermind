"""Lernbereich – Lernstand pro Karte.

learn_card bekommt `status` (open|weak|medium|strong) für den Lernstand-Balken
auf der Startseite und `last_reviewed_at` (Zeitpunkt der letzten Selbst-
einschätzung im Lernmodus). Reine Spalten-Erweiterung; RLS/Grants der Tabelle
bleiben aus 096 bestehen.

Revision ID: 098_learn_card_status
Revises: 097_learn_marker
Create Date: 2026-09-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "098_learn_card_status"
down_revision: Union[str, None] = "097_learn_marker"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learn_card",
        sa.Column("status", sa.String(length=12), nullable=False, server_default="open"),
    )
    op.add_column(
        "learn_card",
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_learn_card_status", "learn_card", ["owner_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_learn_card_status", table_name="learn_card")
    op.drop_column("learn_card", "last_reviewed_at")
    op.drop_column("learn_card", "status")
