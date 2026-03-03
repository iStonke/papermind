"""add display_name to documents and include it in fts

Revision ID: 011_documents_display_name
Revises: 010_ap8_embeddings
Create Date: 2026-02-27 18:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "011_documents_display_name"
down_revision: Union[str, None] = "010_ap8_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("display_name", sa.Text(), nullable=True))

    op.execute(
        """
        CREATE OR REPLACE FUNCTION documents_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.display_name, '')), 'B') ||
                setweight(
                    to_tsvector(
                        'pg_catalog.simple',
                        regexp_replace(coalesce(NEW.display_name, ''), '[^[:alnum:]]+', ' ', 'g')
                    ),
                    'C'
                ) ||
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.original_filename, '')), 'C') ||
                setweight(
                    to_tsvector(
                        'pg_catalog.german',
                        regexp_replace(coalesce(NEW.original_filename, ''), '[^[:alnum:]]+', ' ', 'g')
                    ),
                    'B'
                ) ||
                setweight(
                    to_tsvector(
                        'pg_catalog.simple',
                        regexp_replace(coalesce(NEW.original_filename, ''), '[^[:alnum:]]+', ' ', 'g')
                    ),
                    'D'
                ) ||
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.notes, '')), 'B') ||
                setweight(to_tsvector('pg_catalog.simple', coalesce(NEW.notes, '')), 'C') ||
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.text_content, '')), 'A') ||
                setweight(to_tsvector('pg_catalog.simple', coalesce(NEW.text_content, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_documents_search_vector ON documents;")
    op.execute(
        """
        CREATE TRIGGER trg_documents_search_vector
        BEFORE INSERT OR UPDATE OF original_filename, display_name, notes, text_content
        ON documents
        FOR EACH ROW
        EXECUTE FUNCTION documents_search_vector_update();
        """
    )

    op.execute(
        """
        UPDATE documents
        SET search_vector =
            setweight(to_tsvector('pg_catalog.german', coalesce(display_name, '')), 'B') ||
            setweight(
                to_tsvector(
                    'pg_catalog.simple',
                    regexp_replace(coalesce(display_name, ''), '[^[:alnum:]]+', ' ', 'g')
                ),
                'C'
            ) ||
            setweight(to_tsvector('pg_catalog.german', coalesce(original_filename, '')), 'C') ||
            setweight(
                to_tsvector(
                    'pg_catalog.german',
                    regexp_replace(coalesce(original_filename, ''), '[^[:alnum:]]+', ' ', 'g')
                ),
                'B'
            ) ||
            setweight(
                to_tsvector(
                    'pg_catalog.simple',
                    regexp_replace(coalesce(original_filename, ''), '[^[:alnum:]]+', ' ', 'g')
                ),
                'D'
            ) ||
            setweight(to_tsvector('pg_catalog.german', coalesce(notes, '')), 'B') ||
            setweight(to_tsvector('pg_catalog.simple', coalesce(notes, '')), 'C') ||
            setweight(to_tsvector('pg_catalog.german', coalesce(text_content, '')), 'A') ||
            setweight(to_tsvector('pg_catalog.simple', coalesce(text_content, '')), 'B');
        """
    )


def downgrade() -> None:
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
                setweight(
                    to_tsvector(
                        'pg_catalog.simple',
                        regexp_replace(coalesce(NEW.original_filename, ''), '[^[:alnum:]]+', ' ', 'g')
                    ),
                    'D'
                ) ||
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.notes, '')), 'B') ||
                setweight(to_tsvector('pg_catalog.simple', coalesce(NEW.notes, '')), 'C') ||
                setweight(to_tsvector('pg_catalog.german', coalesce(NEW.text_content, '')), 'A') ||
                setweight(to_tsvector('pg_catalog.simple', coalesce(NEW.text_content, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute("DROP TRIGGER IF EXISTS trg_documents_search_vector ON documents;")
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
            setweight(to_tsvector('pg_catalog.german', coalesce(original_filename, '')), 'C') ||
            setweight(
                to_tsvector(
                    'pg_catalog.german',
                    regexp_replace(coalesce(original_filename, ''), '[^[:alnum:]]+', ' ', 'g')
                ),
                'B'
            ) ||
            setweight(
                to_tsvector(
                    'pg_catalog.simple',
                    regexp_replace(coalesce(original_filename, ''), '[^[:alnum:]]+', ' ', 'g')
                ),
                'D'
            ) ||
            setweight(to_tsvector('pg_catalog.german', coalesce(notes, '')), 'B') ||
            setweight(to_tsvector('pg_catalog.simple', coalesce(notes, '')), 'C') ||
            setweight(to_tsvector('pg_catalog.german', coalesce(text_content, '')), 'A') ||
            setweight(to_tsvector('pg_catalog.simple', coalesce(text_content, '')), 'B');
        """
    )

    op.drop_column("documents", "display_name")
