"""add categories vocabulary table and documents.category column

Revision ID: 030_categories
Revises: 029_ai_classification_fields
Create Date: 2026-05-31 00:00:00.000000
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "030_categories"
down_revision: Union[str, None] = "029_ai_classification_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Startbefüllung – entspricht der bisherigen hartcodierten Frontend-Liste.
_SEED_CATEGORIES = [
    "Rechnungen",
    "Verträge",
    "Briefe",
    "Belege",
    "Steuern",
    "Versicherung",
    "Bank",
]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )
    op.create_index("ix_categories_name", "categories", ["name"], unique=False)

    op.add_column("documents", sa.Column("category", sa.Text(), nullable=True))
    op.create_index("ix_documents_category", "documents", ["category"], unique=False)

    categories_table = sa.table(
        "categories",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.Text()),
    )
    op.bulk_insert(
        categories_table,
        [{"id": uuid.uuid4(), "name": name} for name in _SEED_CATEGORIES],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_category", table_name="documents")
    op.drop_column("documents", "category")
    op.drop_index("ix_categories_name", table_name="categories")
    op.drop_table("categories")
