"""extend doc_chunks chunk_type with bank_details

Revision ID: 016_chunk_type_bank
Revises: 015_doc_chunks_chunk_type
Create Date: 2026-02-28 00:55:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016_chunk_type_bank"
down_revision: Union[str, None] = "015_doc_chunks_chunk_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_doc_chunks_chunk_type", "doc_chunks", type_="check")
    op.create_check_constraint(
        "ck_doc_chunks_chunk_type",
        "doc_chunks",
        "chunk_type IN ('header', 'invoice_table', 'invoice_total', 'bank_details')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_doc_chunks_chunk_type", "doc_chunks", type_="check")
    op.create_check_constraint(
        "ck_doc_chunks_chunk_type",
        "doc_chunks",
        "chunk_type IN ('header', 'invoice_table', 'invoice_total')",
    )
