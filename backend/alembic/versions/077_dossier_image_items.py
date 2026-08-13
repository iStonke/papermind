"""add JPEG and PNG image items to dossier light tables.

Revision ID: 077_dossier_image_items
Revises: 076_chat_retrieval_defaults
Create Date: 2026-08-14 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "077_dossier_image_items"
down_revision: Union[str, None] = "076_chat_retrieval_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dossier_items", sa.Column("image_filename", sa.Text(), nullable=True))
    op.add_column("dossier_items", sa.Column("image_content_type", sa.String(length=32), nullable=True))
    op.add_column("dossier_items", sa.Column("image_file_key", sa.Text(), nullable=True))
    op.add_column("dossier_items", sa.Column("image_size_bytes", sa.Integer(), nullable=True))
    op.add_column("dossier_items", sa.Column("image_width", sa.Integer(), nullable=True))
    op.add_column("dossier_items", sa.Column("image_height", sa.Integer(), nullable=True))

    op.drop_constraint("ck_dossier_items_payload", "dossier_items", type_="check")
    op.drop_constraint("ck_dossier_items_type", "dossier_items", type_="check")
    op.create_check_constraint(
        "ck_dossier_items_type",
        "dossier_items",
        "item_type IN ('document', 'note', 'link', 'image')",
    )
    op.create_check_constraint(
        "ck_dossier_items_payload",
        "dossier_items",
        "(item_type = 'document' AND document_id IS NOT NULL) OR "
        "(item_type = 'note' AND document_id IS NULL) OR "
        "(item_type = 'link' AND document_id IS NULL AND link_url IS NOT NULL) OR "
        "(item_type = 'image' AND document_id IS NULL AND image_file_key IS NOT NULL)",
    )


def downgrade() -> None:
    op.execute("DELETE FROM dossier_items WHERE item_type = 'image'")
    op.drop_constraint("ck_dossier_items_payload", "dossier_items", type_="check")
    op.drop_constraint("ck_dossier_items_type", "dossier_items", type_="check")
    op.create_check_constraint(
        "ck_dossier_items_type",
        "dossier_items",
        "item_type IN ('document', 'note', 'link')",
    )
    op.create_check_constraint(
        "ck_dossier_items_payload",
        "dossier_items",
        "(item_type = 'document' AND document_id IS NOT NULL) OR "
        "(item_type = 'note' AND document_id IS NULL) OR "
        "(item_type = 'link' AND document_id IS NULL AND link_url IS NOT NULL)",
    )

    op.drop_column("dossier_items", "image_height")
    op.drop_column("dossier_items", "image_width")
    op.drop_column("dossier_items", "image_size_bytes")
    op.drop_column("dossier_items", "image_file_key")
    op.drop_column("dossier_items", "image_content_type")
    op.drop_column("dossier_items", "image_filename")
