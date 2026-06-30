"""per-document annotations (highlights, notes, links) as an overlay layer.

Kind-Tabelle von ``documents`` – der Owner wird über das Parent-Dokument
abgeleitet (RLS spiegelt das ``_CHILD_TABLES``-Muster aus Migration 042). Das
Original-PDF bleibt unangetastet; Markierungen leben ausschließlich hier.

Revision ID: 059_document_annotations
Revises: 058_scanner_scan_job_events
Create Date: 2026-06-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "059_document_annotations"
down_revision: Union[str, None] = "058_scanner_scan_job_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "annotations",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), server_default=sa.text("'highlight'"), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("rects", JSONB(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("prefix", sa.Text(), nullable=True),
        sa.Column("suffix", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("target_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("target_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_annotations_document_id", "annotations", ["document_id"], unique=False)
    op.create_index("ix_annotations_document_page", "annotations", ["document_id", "page"], unique=False)

    # RLS: Owner erbt über das Parent-Dokument (wie doc_chunks/jobs in Migration 042).
    cond = (
        f"EXISTS (SELECT 1 FROM documents d "
        f"WHERE d.id = annotations.document_id AND d.owner_id = {_OWNER_EXPR})"
    )
    op.execute("ALTER TABLE annotations ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS annotations_owner_isolation ON annotations")
    op.execute(
        f"CREATE POLICY annotations_owner_isolation ON annotations "
        f"USING ({cond}) WITH CHECK ({cond})"
    )

    # Grants für die nicht-privilegierten Rollen (idempotent; ALTER DEFAULT PRIVILEGES
    # aus Migration 042 deckt neue Tabellen i. d. R. ab, hier explizit zur Sicherheit).
    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON annotations TO "{role}";
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS annotations_owner_isolation ON annotations")
    op.drop_index("ix_annotations_document_page", table_name="annotations")
    op.drop_index("ix_annotations_document_id", table_name="annotations")
    op.drop_table("annotations")
