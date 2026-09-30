"""Lernbereich – typspezifischer Karten-Payload.

learn_card bekommt `payload` (JSONB), damit Lernobjekte über die Flip-Karte
hinaus möglich sind (z. B. Schrittfolge: {"steps": [...]}). Flip-Karten
(Fakt/Verständnis/Übung/Vergleich) lassen das Feld leer ({}). Reine
Spalten-Erweiterung; RLS/Grants der Tabelle bleiben aus 096 bestehen.

Revision ID: 101_learn_card_payload
Revises: 100_learn_marker_context
Create Date: 2026-09-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "101_learn_card_payload"
down_revision: Union[str, None] = "100_learn_marker_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learn_card",
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("learn_card", "payload")
