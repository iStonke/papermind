"""rename categories to document_types

Revision ID: 031_document_types_rename
Revises: 030_categories
Create Date: 2026-06-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "031_document_types_rename"
down_revision: Union[str, None] = "030_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_documents_category", table_name="documents")
    op.alter_column("documents", "category", new_column_name="document_type")
    op.create_index("ix_documents_document_type", "documents", ["document_type"], unique=False)

    op.drop_index("ix_categories_name", table_name="categories")
    op.rename_table("categories", "document_types")
    op.create_index("ix_document_types_name", "document_types", ["name"], unique=False)
    op.execute("ALTER TABLE document_types RENAME CONSTRAINT uq_categories_name TO uq_document_types_name")


def downgrade() -> None:
    op.execute("ALTER TABLE document_types RENAME CONSTRAINT uq_document_types_name TO uq_categories_name")
    op.drop_index("ix_document_types_name", table_name="document_types")
    op.rename_table("document_types", "categories")
    op.create_index("ix_categories_name", "categories", ["name"], unique=False)

    op.drop_index("ix_documents_document_type", table_name="documents")
    op.alter_column("documents", "document_type", new_column_name="category")
    op.create_index("ix_documents_category", "documents", ["category"], unique=False)
