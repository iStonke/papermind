"""Lernbereich – Container-Ebene: Kurs, Sitzung, Lernblatt.

Erste echte Tabellen des dritten Bereichs „Lernen" (siehe
docs/design/lernbereich-datenmodell.md §3.1/§3.3/§3.8). Bewusst nur die
Container-Ebene: Karten/Artefakte, Anker und die Marker-Projektion folgen in
einer späteren Migration (sie hängen an den stabilen Node-IDs im Notiz-JSON und
an den noch offenen Ablage-Entscheidungen).

Alle Tabellen owner-scoped mit RLS-Isolation analog Migration 041/093.

Revision ID: 095_learn_core
Revises: 095_note_last_opened
Create Date: 2026-09-21 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "095_learn_core"
down_revision: Union[str, None] = "095_note_last_opened"
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


def _enable_rls(table: str) -> None:
    owner_check = f"owner_id = {_OWNER_EXPR}"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_owner_isolation ON {table} "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant(table)


def upgrade() -> None:
    # --- learn_course -------------------------------------------------------
    op.create_table(
        "learn_course",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("module_key", sa.String(length=64), nullable=True),
        sa.Column("default_artifact_type", sa.String(length=24), nullable=False, server_default="fakt"),
        sa.Column("has_script", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learn_course_owner", "learn_course", ["owner_id", "position", "title"])
    _enable_rls("learn_course")

    # --- learn_session ------------------------------------------------------
    op.create_table(
        "learn_session",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=True),
        sa.Column("note_id", UUID(as_uuid=True), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["learn_course.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["note_id"], ["note.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learn_session_owner", "learn_session", ["owner_id"])
    op.create_index("ix_learn_session_course", "learn_session", ["course_id", "ordinal"])
    _enable_rls("learn_session")

    # --- learn_sheet --------------------------------------------------------
    op.create_table(
        "learn_sheet",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=12), nullable=False, server_default="session"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("structure", JSONB(), nullable=False, server_default="{}"),
        sa.Column("source_label", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["learn_course.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["learn_session.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learn_sheet_owner", "learn_sheet", ["owner_id"])
    op.create_index("ix_learn_sheet_course", "learn_sheet", ["course_id", "position"])
    op.create_index("ix_learn_sheet_session", "learn_sheet", ["session_id"])
    _enable_rls("learn_sheet")


def downgrade() -> None:
    for table in ("learn_sheet", "learn_session", "learn_course"):
        op.execute(f"DROP POLICY IF EXISTS {table}_owner_isolation ON {table}")
    op.drop_table("learn_sheet")
    op.drop_table("learn_session")
    op.drop_table("learn_course")
