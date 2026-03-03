"""improve documents fts filename tokenization

Revision ID: 005_fts_filename_tokens
Revises: 004_documents_fts
Create Date: 2026-02-27 01:25:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_fts_filename_tokens"
down_revision: Union[str, None] = "004_documents_fts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION documents_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.original_filename, '')), 'C') ||
                setweight(
                    to_tsvector(
                        'pg_catalog.german',
                        regexp_replace(coalesce(NEW.original_filename, ''), '[^[:alnum:]]+', ' ', 'g')
                    ),
                    'B'
                ) ||
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.notes, '')), 'B') ||
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.text_content, '')), 'A');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        UPDATE documents
        SET search_vector =
            setweight(to_tsvector('pg_catalog.german', coalesce(original_filename, '')), 'C') ||
            setweight(
                to_tsvector(
                    'pg_catalog.german',
                    regexp_replace(coalesce(original_filename, ''), '[^[:alnum:]]+', ' ', 'g')
                ),
                'B'
            ) ||
            setweight(to_tsvector('pg_catalog.german', coalesce(notes, '')), 'B') ||
            setweight(to_tsvector('pg_catalog.german', coalesce(text_content, '')), 'A');
        """
    )


def downgrade() -> None:
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
        UPDATE documents
        SET search_vector =
            setweight(to_tsvector('pg_catalog.german', coalesce(original_filename, '')), 'B') ||
            setweight(to_tsvector('pg_catalog.german', coalesce(notes, '')), 'B') ||
            setweight(to_tsvector('pg_catalog.german', coalesce(text_content, '')), 'A');
        """
    )
