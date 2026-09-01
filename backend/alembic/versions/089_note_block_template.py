"""Owner-scoped block templates (reusable field-box presets).

Benutzereigene Bausteine für den Vorlagenfeld-Block (``templateBox``): Titel,
Farbe und Feldzeilen. Getrennt von den Ganz-Notiz-Vorlagen (``note.is_template``).

Revision ID: 089_note_block_template
Revises: 088_note_history
Create Date: 2026-08-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "089_note_block_template"
down_revision: Union[str, None] = "088_note_history"
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
        "note_block_template",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("color", sa.String(length=32), nullable=False, server_default="teal"),
        sa.Column("fields", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_note_block_template_owner_updated",
        "note_block_template",
        ["owner_id", "updated_at"],
    )

    # Direkte Eigentümer-Isolation (analog note/tag): owner_id == app.owner_id.
    owner_check = f"owner_id = {_OWNER_EXPR}"
    op.execute("ALTER TABLE note_block_template ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_block_template_owner_isolation ON note_block_template "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("note_block_template")


def downgrade() -> None:
    op.execute("DROP POLICY note_block_template_owner_isolation ON note_block_template")
    op.drop_index("ix_note_block_template_owner_updated", table_name="note_block_template")
    op.drop_table("note_block_template")
