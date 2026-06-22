"""add type (kind) and parent hierarchy to correspondents

Revision ID: 050_correspondent_type_hierarchy
Revises: 049_auth_sessions_jobs
Create Date: 2026-06-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "050_correspondent_type_hierarchy"
down_revision: Union[str, None] = "049_auth_sessions_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive only: bestehende Korrespondenten bleiben unangetastet (kind = NULL =
    # "noch nicht typisiert"). Die Typisierung des Altbestands erfolgt separat.
    op.add_column("correspondents", sa.Column("kind", sa.Text(), nullable=True))
    op.add_column(
        "correspondents",
        sa.Column("parent_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_correspondents_parent_id",
        "correspondents",
        "correspondents",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_correspondents_parent_id", "correspondents", ["parent_id"], unique=False)
    op.create_check_constraint(
        "ck_correspondents_kind",
        "correspondents",
        "kind IS NULL OR kind IN ('organization', 'person')",
    )
    op.create_check_constraint(
        "ck_correspondents_parent_only_person",
        "correspondents",
        "parent_id IS NULL OR kind = 'person'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_correspondents_parent_only_person", "correspondents", type_="check")
    op.drop_constraint("ck_correspondents_kind", "correspondents", type_="check")
    op.drop_index("ix_correspondents_parent_id", table_name="correspondents")
    op.drop_constraint("fk_correspondents_parent_id", "correspondents", type_="foreignkey")
    op.drop_column("correspondents", "parent_id")
    op.drop_column("correspondents", "kind")
