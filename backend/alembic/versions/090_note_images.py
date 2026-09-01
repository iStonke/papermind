"""Owner-scoped image assets for the notes editor.

Revision ID: 090_note_images
Revises: 089_note_block_template
Create Date: 2026-08-31 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "090_note_images"
down_revision: Union[str, None] = "089_note_block_template"
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
        "note_image",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("file_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["note_id"], ["note.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_key", name="uq_note_image_file_key"),
    )
    op.create_index("ix_note_image_note_created", "note_image", ["note_id", "created_at"])
    op.create_index("ix_note_image_owner_created", "note_image", ["owner_id", "created_at"])

    op.execute("ALTER TABLE note_image ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_image_owner_isolation ON note_image "
        f"USING (owner_id = {_OWNER_EXPR}) WITH CHECK (owner_id = {_OWNER_EXPR})"
    )
    _grant("note_image")
    op.execute(
        "CREATE TRIGGER backup_source_dirty_note_image "
        "AFTER INSERT OR UPDATE OR DELETE ON note_image "
        "FOR EACH STATEMENT EXECUTE FUNCTION mark_backup_source_dirty()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER backup_source_dirty_note_image ON note_image")
    op.execute("DROP POLICY note_image_owner_isolation ON note_image")
    op.drop_index("ix_note_image_owner_created", table_name="note_image")
    op.drop_index("ix_note_image_note_created", table_name="note_image")
    op.drop_table("note_image")
