"""add documents fts search vector

Revision ID: 004_documents_fts
Revises: 003_ocr_pipeline_fields
Create Date: 2026-02-27 00:40:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_documents_fts"
down_revision: Union[str, None] = "003_ocr_pipeline_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True))

    op.execute(
        """
        CREATE OR REPLACE FUNCTION documents_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.original_filename, '')), 'B') ||
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.notes, '')), 'B') ||
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.text_content, '')), 'A');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_documents_search_vector
        BEFORE INSERT OR UPDATE OF original_filename, notes, text_content
        ON documents
        FOR EACH ROW
        EXECUTE FUNCTION documents_search_vector_update();
        """
    )

    op.execute(
        """
        UPDATE documents
        SET search_vector =
            setweight(to_tsvector('pg_catalog.german', coalesce(original_filename, '')), 'B') ||
            setweight(to_tsvector('pg_catalog.german', coalesce(notes, '')), 'B') ||
            setweight(to_tsvector('pg_catalog.german', coalesce(text_content, '')), 'A');
        """
    )

    op.create_index(
        "ix_documents_search_vector",
        "documents",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_documents_search_vector", table_name="documents")
    op.execute("DROP TRIGGER IF EXISTS trg_documents_search_vector ON documents;")
    op.execute("DROP FUNCTION IF EXISTS documents_search_vector_update;")
    op.drop_column("documents", "search_vector")
