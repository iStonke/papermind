"""add correspondents, aliases, matchers and documents.correspondent_id

Revision ID: 033_correspondents
Revises: 032_document_type_metadata_seed
Create Date: 2026-06-02 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "033_correspondents"
down_revision: Union[str, None] = "032_document_type_metadata_seed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "correspondents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_correspondents_name"),
    )
    op.create_index("ix_correspondents_name", "correspondents", ["name"], unique=False)

    op.create_table(
        "correspondent_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correspondent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["correspondent_id"], ["correspondents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_correspondent_aliases_correspondent_id",
        "correspondent_aliases",
        ["correspondent_id"],
        unique=False,
    )
    # Pro Korrespondent ist ein Alias case-insensitiv eindeutig.
    op.execute(
        "CREATE UNIQUE INDEX uq_correspondent_aliases_lower "
        "ON correspondent_aliases (correspondent_id, lower(alias))"
    )

    op.create_table(
        "correspondent_matchers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correspondent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), server_default="contains", nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), server_default="both", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.ForeignKeyConstraint(["correspondent_id"], ["correspondents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('contains', 'regex', 'starts_with')", name="ck_correspondent_matchers_kind"),
        sa.CheckConstraint("scope IN ('filename', 'ocr_text', 'both')", name="ck_correspondent_matchers_scope"),
    )
    op.create_index(
        "ix_correspondent_matchers_correspondent_id",
        "correspondent_matchers",
        ["correspondent_id"],
        unique=False,
    )
    op.create_index("ix_correspondent_matchers_priority", "correspondent_matchers", ["priority"], unique=False)

    op.add_column(
        "documents",
        sa.Column("correspondent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_correspondent_id",
        "documents",
        "correspondents",
        ["correspondent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_documents_correspondent_id", "documents", ["correspondent_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_documents_correspondent_id", table_name="documents")
    op.drop_constraint("fk_documents_correspondent_id", "documents", type_="foreignkey")
    op.drop_column("documents", "correspondent_id")

    op.drop_index("ix_correspondent_matchers_priority", table_name="correspondent_matchers")
    op.drop_index("ix_correspondent_matchers_correspondent_id", table_name="correspondent_matchers")
    op.drop_table("correspondent_matchers")

    op.drop_index("uq_correspondent_aliases_lower", table_name="correspondent_aliases")
    op.drop_index("ix_correspondent_aliases_correspondent_id", table_name="correspondent_aliases")
    op.drop_table("correspondent_aliases")

    op.drop_index("ix_correspondents_name", table_name="correspondents")
    op.drop_table("correspondents")
