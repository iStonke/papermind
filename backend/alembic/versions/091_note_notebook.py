"""Notizbücher: leichte, flache Ablageebene für Notizen (genau eine Ebene).

Ein Notizbuch ist ein owner-scoped Objekt (analog ``smart_folders``/``tags``).
Notizen tragen eine optionale ``notebook_id`` (nullable FK); ``NULL`` bedeutet
„Ohne Notizbuch". Bewusst keine Hierarchie: Notizbücher sind Heimathäfen, die
eigentliche Skalierung übernehmen Tags, Verweise und gespeicherte Ansichten.

Revision ID: 091_note_notebook
Revises: 090_note_images
Create Date: 2026-09-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "091_note_notebook"
down_revision: Union[str, None] = "090_note_images"
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
        "note_notebook",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "name", name="uq_note_notebook_owner_name"),
    )
    op.create_index("ix_note_notebook_owner", "note_notebook", ["owner_id", "position", "name"])

    op.add_column("note", sa.Column("notebook_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_note_notebook_id",
        "note",
        "note_notebook",
        ["notebook_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_note_owner_notebook", "note", ["owner_id", "notebook_id"])

    owner_check = f"owner_id = {_OWNER_EXPR}"
    op.execute("ALTER TABLE note_notebook ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_notebook_owner_isolation ON note_notebook "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("note_notebook")


def downgrade() -> None:
    op.execute("DROP POLICY note_notebook_owner_isolation ON note_notebook")
    op.drop_index("ix_note_owner_notebook", table_name="note")
    op.drop_constraint("fk_note_notebook_id", "note", type_="foreignkey")
    op.drop_column("note", "notebook_id")
    op.drop_index("ix_note_notebook_owner", table_name="note_notebook")
    op.drop_table("note_notebook")
