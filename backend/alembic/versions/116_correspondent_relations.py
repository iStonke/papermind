"""Seitliche Verbindungen zwischen Korrespondenten (Nachfolger, handelt für).

Ergänzt die Zwei-Ebenen-Hierarchie (Organisation → Person, ``parent_id``) um
gerichtete Verbindungen: ``successor`` (Vorgänger → Nachfolger nach
Umbenennung/Fusion) und ``acts_for`` (Beauftragter → Auftraggeber).
Owner-scoped mit RLS analog 108.

Revision ID: 116_correspondent_relations
Revises: 115_knowledge_corrections
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


revision: str = "116_correspondent_relations"
down_revision: Union[str, None] = "115_knowledge_corrections"
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
        "correspondent_relations",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["correspondents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["correspondents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "target_id", "kind", name="uq_correspondent_relations_pair"),
        sa.CheckConstraint("kind IN ('successor', 'acts_for')", name="ck_correspondent_relations_kind"),
        sa.CheckConstraint("source_id <> target_id", name="ck_correspondent_relations_distinct"),
    )
    op.create_index("ix_correspondent_relations_owner_id", "correspondent_relations", ["owner_id"])
    op.create_index("ix_correspondent_relations_target_id", "correspondent_relations", ["target_id"])
    op.create_index(
        "uq_correspondent_relations_single_successor",
        "correspondent_relations",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'successor'"),
    )

    owner_check = f"owner_id = {_OWNER_EXPR}"
    op.execute("ALTER TABLE correspondent_relations ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY correspondent_relations_owner_isolation ON correspondent_relations "
        f"USING ({owner_check}) WITH CHECK ({owner_check})"
    )
    _grant("correspondent_relations")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS correspondent_relations_owner_isolation ON correspondent_relations")
    op.drop_table("correspondent_relations")
