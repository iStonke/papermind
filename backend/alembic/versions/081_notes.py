"""First-class notes: born-digital notes as an owner-scoped object.

Nur die `note`-Kerntabelle (Editor-Persistenz). Die Verknüpfungstabellen
`note_link`/`note_attachment` folgen erst mit M4/M5, wenn Reader-Verankerung und
Rückverweise sie tatsächlich beschreiben.

Revision ID: 081_notes
Revises: 080_per_scanner_live_page_mode
Create Date: 2026-08-23 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID


revision: str = "081_notes"
down_revision: Union[str, None] = "080_per_scanner_live_page_mode"
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
        "note",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        # Quelle der Wahrheit: ProseMirror-JSON. body_text wird daraus abgeleitet
        # (Service) und speist den Volltextindex.
        sa.Column("body_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("search_vector", TSVECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_note_owner_id", "note", ["owner_id"])
    op.create_index("ix_note_owner_updated", "note", ["owner_id", "updated_at"])
    op.create_index("ix_note_search_vector", "note", ["search_vector"], postgresql_using="gin")

    # Volltext: Titel (Gewicht A) + abgeleiteter Body-Text (B), plus 'simple'-
    # Fallback (C) für exakte Tokens. Deutsch, konsistent zu Dokumenten/Wiki.
    op.execute(
        """
        CREATE FUNCTION update_note_search_vector()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.search_vector =
                setweight(to_tsvector('german', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('german', coalesce(NEW.body_text, '')), 'B') ||
                setweight(to_tsvector('simple', coalesce(NEW.title, '') || ' ' || coalesce(NEW.body_text, '')), 'C');
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER note_search_vector_update BEFORE INSERT OR UPDATE OF title, body_text "
        "ON note FOR EACH ROW EXECUTE FUNCTION update_note_search_vector()"
    )

    # Pro-Benutzer-Isolation (RLS), analog Dossiers/Dokumenten.
    op.execute("ALTER TABLE note ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY note_owner_isolation ON note "
        f"USING (owner_id = {_OWNER_EXPR}) WITH CHECK (owner_id = {_OWNER_EXPR})"
    )
    _grant("note")

    # In die Backup-Dirty-Verfolgung einklinken (wie andere Nutzdaten-Tabellen).
    op.execute(
        "CREATE TRIGGER backup_source_dirty_note "
        "AFTER INSERT OR UPDATE OR DELETE ON note "
        "FOR EACH STATEMENT EXECUTE FUNCTION mark_backup_source_dirty()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER backup_source_dirty_note ON note")
    op.execute("DROP POLICY note_owner_isolation ON note")
    op.execute("DROP TRIGGER note_search_vector_update ON note")
    op.execute("DROP FUNCTION update_note_search_vector()")
    op.drop_index("ix_note_search_vector", table_name="note")
    op.drop_index("ix_note_owner_updated", table_name="note")
    op.drop_index("ix_note_owner_id", table_name="note")
    op.drop_table("note")
