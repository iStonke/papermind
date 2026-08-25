"""Notiz-Vorlagen: is_template-Flag auf note.

Eine Vorlage IST eine Notiz (gleiche Tabelle, Editor-Pipeline, RLS), nur mit
gesetztem ``is_template``. Vorlagen erscheinen nicht in der normalen Notizliste
und erzeugen keine note_link-Rückverweise; „Neue Notiz aus Vorlage" kopiert
body_json in eine frische, reguläre Notiz.

Revision ID: 084_note_templates
Revises: 083_note_links
Create Date: 2026-08-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "084_note_templates"
down_revision: Union[str, None] = "083_note_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "note",
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Teilindex: schneller Zugriff auf die (wenigen) Vorlagen je Eigentümer.
    op.create_index(
        "ix_note_owner_template",
        "note",
        ["owner_id", "updated_at"],
        unique=False,
        postgresql_where=sa.text("is_template"),
    )


def downgrade() -> None:
    op.drop_index("ix_note_owner_template", table_name="note")
    op.drop_column("note", "is_template")
