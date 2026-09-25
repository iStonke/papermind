"""Lernbereich – Karten (Artefakte) innerhalb eines Lernblatts.

Vereinfachte Artefakt-Ebene (Datenmodell §3.6): Lerntyp + Vorder-/Rückseite.
Anker/Herkunft/Prüf-Status folgen mit der Notiz-Marker-Anbindung. Owner-scoped
mit RLS analog 095.

Revision ID: 096_learn_card
Revises: 095_learn_core
Create Date: 2026-09-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "096_learn_card"
down_revision: Union[str, None] = "095_learn_core"
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
        "learn_card",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sheet_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False, server_default="fakt"),
        sa.Column("front", sa.Text(), nullable=False, server_default=""),
        sa.Column("back", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sheet_id"], ["learn_sheet.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learn_card_owner", "learn_card", ["owner_id"])
    op.create_index("ix_learn_card_sheet", "learn_card", ["sheet_id", "position"])

    owner_check = f"owner_id = {_OWNER_EXPR}"
    op.execute("ALTER TABLE learn_card ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY learn_card_owner_isolation ON learn_card "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("learn_card")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS learn_card_owner_isolation ON learn_card")
    op.drop_table("learn_card")
