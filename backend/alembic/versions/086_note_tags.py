"""Notiz-Tags: Wiederverwendung der bestehenden tags-Tabelle für Notizen.

Spiegelt document_tags: eine reine Verknüpfungstabelle (note_id ↔ tag_id) auf
derselben ``tags``-Tabelle, sodass Tags ein gemeinsames Vokabular für Dokumente
UND Notizen bilden. RLS über die Eigentümerschaft der zugehörigen Notiz.

Revision ID: 086_note_tags
Revises: 085_note_tasks
Create Date: 2026-08-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "086_note_tags"
down_revision: Union[str, None] = "085_note_tasks"
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
        "note_tags",
        sa.Column("note_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["note_id"], ["note.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("note_id", "tag_id"),
    )
    op.create_index("ix_note_tags_note_id", "note_tags", ["note_id"])
    op.create_index("ix_note_tags_tag_id", "note_tags", ["tag_id"])

    # RLS über die Eigentümerschaft der zugehörigen Notiz (analog note_link).
    owner_check = (
        "EXISTS (SELECT 1 FROM note n WHERE n.id = note_tags.note_id "
        f"AND n.owner_id = {_OWNER_EXPR})"
    )
    op.execute("ALTER TABLE note_tags ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_tags_owner_isolation ON note_tags "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("note_tags")


def downgrade() -> None:
    op.execute("DROP POLICY note_tags_owner_isolation ON note_tags")
    op.drop_index("ix_note_tags_tag_id", table_name="note_tags")
    op.drop_index("ix_note_tags_note_id", table_name="note_tags")
    op.drop_table("note_tags")
