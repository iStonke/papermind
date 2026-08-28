"""Zeitlich gebündelter Versionsverlauf für Notizen.

Revision ID: 088_note_history
Revises: 087_note_revision
Create Date: 2026-08-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "088_note_history"
down_revision: Union[str, None] = "087_note_revision"
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
        "note_revision",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("note_revision", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=24), nullable=False, server_default="autosave"),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("note_revision > 0", name="ck_note_revision_number"),
        sa.CheckConstraint(
            "reason IN ('created', 'autosave', 'navigation', 'export', 'ai', "
            "'before_restore', 'restore', 'manual')",
            name="ck_note_revision_reason",
        ),
        sa.ForeignKeyConstraint(["note_id"], ["note.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("note_id", "note_revision", name="uq_note_revision_note_number"),
    )
    op.create_index("ix_note_revision_note_updated", "note_revision", ["note_id", "updated_at"])
    op.create_index("ix_note_revision_owner_updated", "note_revision", ["owner_id", "updated_at"])

    op.execute("ALTER TABLE note_revision ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_revision_owner_isolation ON note_revision "
        f"USING (owner_id = {_OWNER_EXPR}) WITH CHECK (owner_id = {_OWNER_EXPR})"
    )
    _grant("note_revision")

    op.execute(
        "CREATE TRIGGER backup_source_dirty_note_revision "
        "AFTER INSERT OR UPDATE OR DELETE ON note_revision "
        "FOR EACH STATEMENT EXECUTE FUNCTION mark_backup_source_dirty()"
    )

    # Bestehende Notizen erhalten einen belastbaren Ausgangsstand, damit der
    # Verlauf nicht erst nach der nächsten Bearbeitung beginnt.
    op.execute(
        """
        INSERT INTO note_revision (
            id, note_id, owner_id, note_revision, reason, title,
            body_json, body_text, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), id, owner_id, revision, 'created', title,
            body_json, body_text, created_at, updated_at
        FROM note
        WHERE NOT is_template
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER backup_source_dirty_note_revision ON note_revision")
    op.execute("DROP POLICY note_revision_owner_isolation ON note_revision")
    op.drop_index("ix_note_revision_owner_updated", table_name="note_revision")
    op.drop_index("ix_note_revision_note_updated", table_name="note_revision")
    op.drop_table("note_revision")
