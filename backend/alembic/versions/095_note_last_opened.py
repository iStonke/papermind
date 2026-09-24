"""Speichert den letzten echten Editor-Aufruf einer Notiz.

Revision ID: 095_note_last_opened
Revises: 094_backup_change_journal
Create Date: 2026-09-24 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "095_note_last_opened"
down_revision: Union[str, None] = "094_backup_change_journal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("note", sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_note_owner_last_opened",
        "note",
        ["owner_id", "last_opened_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_note_owner_last_opened", table_name="note")
    op.drop_column("note", "last_opened_at")
