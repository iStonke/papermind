"""Optimistischer Revisionsschutz für Notiz-Autosave.

Revision ID: 087_note_revision
Revises: 086_note_tags
Create Date: 2026-08-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "087_note_revision"
down_revision: Union[str, None] = "086_note_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "note",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("note", "revision")
