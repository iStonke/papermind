"""persistent source-linked document wiki pages.

Revision ID: 066_document_wiki_entries
Revises: 065_chat_latency_defaults
Create Date: 2026-07-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "066_document_wiki_entries"
down_revision: Union[str, None] = "065_chat_latency_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "document_wiki_entries",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_text_hash", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
    )
    condition = (
        f"EXISTS (SELECT 1 FROM documents d "
        f"WHERE d.id = document_wiki_entries.document_id AND d.owner_id = {_OWNER_EXPR})"
    )
    op.execute("ALTER TABLE document_wiki_entries ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY document_wiki_entries_owner_isolation ON document_wiki_entries "
        f"USING ({condition}) WITH CHECK ({condition})"
    )
    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON document_wiki_entries TO \"{role}\";
              END IF;
            END $$;
            """
        )
    # Die Backup-Generation muss auch bei einer reinen Wiki-Aktualisierung steigen.
    op.execute(
        "CREATE TRIGGER backup_source_dirty_document_wiki_entries "
        "AFTER INSERT OR UPDATE OR DELETE ON document_wiki_entries "
        "FOR EACH STATEMENT EXECUTE FUNCTION mark_backup_source_dirty()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER backup_source_dirty_document_wiki_entries ON document_wiki_entries")
    op.execute("DROP POLICY document_wiki_entries_owner_isolation ON document_wiki_entries")
    op.drop_table("document_wiki_entries")
