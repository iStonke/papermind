"""switch embeddings to 1024 dimensions (bge-m3) and reset for re-embedding

The previous embeddings were 384-dim hash stubs. Real semantic embeddings via
Ollama (bge-m3) are 1024-dim, so the vector column + HNSW index must be widened.
Existing chunks/embeddings are cleared and all documents are flagged for
re-embedding (the old hash vectors carry no meaning and are incompatible).

Revision ID: 038_embeddings_dim_1024
Revises: 037_users
Create Date: 2026-06-07 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "038_embeddings_dim_1024"
down_revision: Union[str, None] = "037_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_DIM = 1024
OLD_DIM = 384


def upgrade() -> None:
    # 1. Drop the ANN index (must be recreated for the new dimension).
    op.execute("DROP INDEX IF EXISTS ix_doc_embeddings_embedding_hnsw;")

    # 2. Clear chunks + embeddings (cascade). Old hash vectors are worthless and
    #    have the wrong dimension; documents are re-chunked + re-embedded.
    op.execute("TRUNCATE TABLE doc_chunks CASCADE;")

    # 3. Widen the vector column to the new dimension (table is now empty).
    op.execute(f"ALTER TABLE doc_embeddings ALTER COLUMN embedding TYPE vector({NEW_DIM});")

    # 4. Recreate the HNSW cosine index.
    op.execute(
        "CREATE INDEX ix_doc_embeddings_embedding_hnsw "
        "ON doc_embeddings USING hnsw (embedding vector_cosine_ops);"
    )

    # 5. Flag every document for re-embedding.
    op.execute(
        """
        UPDATE documents
        SET embedding_status = 'not_started',
            embedding_model = NULL,
            embedding_dim = NULL,
            embedding_error = NULL,
            embedding_updated_at = NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_doc_embeddings_embedding_hnsw;")
    op.execute("TRUNCATE TABLE doc_chunks CASCADE;")
    op.execute(f"ALTER TABLE doc_embeddings ALTER COLUMN embedding TYPE vector({OLD_DIM});")
    op.execute(
        "CREATE INDEX ix_doc_embeddings_embedding_hnsw "
        "ON doc_embeddings USING hnsw (embedding vector_cosine_ops);"
    )
    op.execute(
        """
        UPDATE documents
        SET embedding_status = 'not_started',
            embedding_model = NULL,
            embedding_dim = NULL,
            embedding_error = NULL,
            embedding_updated_at = NULL
        """
    )
