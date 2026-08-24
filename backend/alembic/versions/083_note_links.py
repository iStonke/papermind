"""Denormalized references from notes to other objects (backlinks).

Beim Speichern einer Notiz werden ihre Verweise (root linkedDocument, wikiLink,
documentChip, ocrQuote) aus body_json extrahiert und hier als Zeilen abgelegt.
So sind Rückverweise („was verweist auf X?") schnell und ohne rekursive
JSONB-Suche abfragbar.

Revision ID: 083_note_links
Revises: 082_note_trash
Create Date: 2026-08-24 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "083_note_links"
down_revision: Union[str, None] = "082_note_trash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def _grant(table: str) -> None:
    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO "{role}";
              END IF;
            END $$;
            """
        )


def upgrade() -> None:
    op.create_table(
        "note_link",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "target_type IN ('document', 'correspondent', 'dossier', 'note')",
            name="ck_note_link_target_type",
        ),
        sa.ForeignKeyConstraint(["note_id"], ["note.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_note_link_note_id", "note_link", ["note_id"])
    op.create_index("ix_note_link_target", "note_link", ["target_type", "target_id"])
    op.create_index(
        "uq_note_link_unique",
        "note_link",
        ["note_id", "target_type", "target_id"],
        unique=True,
    )

    # RLS über die Eigentümerschaft der zugehörigen Notiz.
    owner_check = (
        "EXISTS (SELECT 1 FROM note n WHERE n.id = note_link.note_id "
        f"AND n.owner_id = {_OWNER_EXPR})"
    )
    op.execute("ALTER TABLE note_link ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_link_owner_isolation ON note_link "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("note_link")


def downgrade() -> None:
    op.execute("DROP POLICY note_link_owner_isolation ON note_link")
    op.drop_index("uq_note_link_unique", table_name="note_link")
    op.drop_index("ix_note_link_target", table_name="note_link")
    op.drop_index("ix_note_link_note_id", table_name="note_link")
    op.drop_table("note_link")
