"""Lernbereich – Marker-Projektion aus Notizen + Karten-Herkunft.

learn_marker: aus dem Notiz-JSON projizierte, als lernrelevant markierte Zeilen
(attrs.learn + stabile attrs.pmId), Muster wie note_task. learn_card bekommt
source_note_id/source_pm_id, damit „offene" Marker = Marker ohne zugehörige
Karte bestimmbar sind. Owner-scoped mit RLS analog 095/096.

Revision ID: 097_learn_marker
Revises: 096_learn_card
Create Date: 2026-09-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "097_learn_marker"
down_revision: Union[str, None] = "096_learn_card"
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
    # --- learn_card: Herkunft der Karte ------------------------------------
    op.add_column("learn_card", sa.Column("source_note_id", UUID(as_uuid=True), nullable=True))
    op.add_column("learn_card", sa.Column("source_pm_id", sa.String(length=16), nullable=True))
    op.create_foreign_key(
        "fk_learn_card_source_note", "learn_card", "note", ["source_note_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_learn_card_source", "learn_card", ["source_note_id", "source_pm_id"])

    # --- learn_marker (Projektion) -----------------------------------------
    op.create_table(
        "learn_marker",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("note_id", UUID(as_uuid=True), nullable=False),
        sa.Column("node_pm_id", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="lernen"),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["note_id"], ["note.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("note_id", "node_pm_id", name="uq_learn_marker_note_node"),
    )
    op.create_index("ix_learn_marker_owner", "learn_marker", ["owner_id"])
    op.create_index("ix_learn_marker_note", "learn_marker", ["note_id"])

    owner_check = f"owner_id = {_OWNER_EXPR}"
    op.execute("ALTER TABLE learn_marker ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY learn_marker_owner_isolation ON learn_marker "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("learn_marker")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS learn_marker_owner_isolation ON learn_marker")
    op.drop_table("learn_marker")
    op.drop_index("ix_learn_card_source", table_name="learn_card")
    op.drop_constraint("fk_learn_card_source_note", "learn_card", type_="foreignkey")
    op.drop_column("learn_card", "source_pm_id")
    op.drop_column("learn_card", "source_note_id")
