"""Denormalized tasks extracted from note taskItem nodes.

Beim Speichern einer Notiz werden ihre Aufgaben (``taskItem``) aus body_json
extrahiert und hier abgelegt. So lassen sich offene/fällige Aufgaben über alle
Notizen hinweg schnell abfragen (Dashboard-Kachel) ohne rekursive JSONB-Suche.

Revision ID: 085_note_tasks
Revises: 084_note_templates
Create Date: 2026-08-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "085_note_tasks"
down_revision: Union[str, None] = "084_note_templates"
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
        "note_task",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("done", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["note_id"], ["note.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_note_task_note_id", "note_task", ["note_id"])
    # Offene, datierte Aufgaben schnell nach Fälligkeit sortieren.
    op.create_index(
        "ix_note_task_open_due",
        "note_task",
        ["due_date"],
        postgresql_where=sa.text("NOT done"),
    )

    # RLS über die Eigentümerschaft der zugehörigen Notiz (analog note_link).
    owner_check = (
        "EXISTS (SELECT 1 FROM note n WHERE n.id = note_task.note_id "
        f"AND n.owner_id = {_OWNER_EXPR})"
    )
    op.execute("ALTER TABLE note_task ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_task_owner_isolation ON note_task "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("note_task")


def downgrade() -> None:
    op.execute("DROP POLICY note_task_owner_isolation ON note_task")
    op.drop_index("ix_note_task_open_due", table_name="note_task")
    op.drop_index("ix_note_task_note_id", table_name="note_task")
    op.drop_table("note_task")
