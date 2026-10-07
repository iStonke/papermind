"""Lernmarkierungen in PDFs, die zu einer Notiz gehören.

Eigene Ebene neben den Lesemodus-Markierungen (``annotations``): Eine
Lernmarkierung entsteht in der Split-Ansicht Notiz↔Dokument, gehört genau einer
Notiz und trägt eine von drei festen Bedeutungen (wichtig/Definition/unklar).
Der Lesemodus arbeitet ausschließlich auf ``annotations`` und kann diese Zeilen
daher weder ändern noch löschen. Owner-scoped mit RLS analog 097.

Revision ID: 108_note_learn_highlight
Revises: 107_ocr_unpaper_off
Create Date: 2026-10-07 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "108_note_learn_highlight"
down_revision: Union[str, None] = "107_ocr_unpaper_off"
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
        "note_learn_highlight",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False),
        sa.Column("rects", JSONB(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["note_id"], ["note.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "color IN ('important', 'definition', 'unclear')",
            name="ck_note_learn_highlight_color",
        ),
        sa.CheckConstraint("page >= 1", name="ck_note_learn_highlight_page"),
    )
    op.create_index("ix_note_learn_highlight_owner", "note_learn_highlight", ["owner_id"])
    op.create_index("ix_note_learn_highlight_note", "note_learn_highlight", ["note_id"])
    op.create_index(
        "ix_note_learn_highlight_document_page", "note_learn_highlight", ["document_id", "page"]
    )

    owner_check = f"owner_id = {_OWNER_EXPR}"
    op.execute("ALTER TABLE note_learn_highlight ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_learn_highlight_owner_isolation ON note_learn_highlight "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("note_learn_highlight")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS note_learn_highlight_owner_isolation ON note_learn_highlight")
    op.drop_table("note_learn_highlight")
