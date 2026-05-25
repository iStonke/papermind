"""documents: is_deleted / deleted_at / is_favorite

Revision ID: 024_documents_trash_favorite
Revises: 023_missing_indexes
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "024_documents_trash_favorite"
down_revision = "023_missing_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="false"))

    # Partieller Index – nur gelöschte Dokumente (klein, schnell)
    op.create_index(
        "ix_documents_is_deleted",
        "documents",
        ["is_deleted"],
        unique=False,
        postgresql_where=sa.text("is_deleted = true"),
    )
    op.create_index(
        "ix_documents_is_favorite",
        "documents",
        ["is_favorite"],
        unique=False,
        postgresql_where=sa.text("is_favorite = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_is_favorite", table_name="documents")
    op.drop_index("ix_documents_is_deleted", table_name="documents")
    op.drop_column("documents", "is_favorite")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "is_deleted")
