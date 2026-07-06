"""composite partial indexes for correspondent/document-type usage counts.

Beschleunigt die usage_count-Aggregationen der Einstellungslisten
(``list_correspondents``/``list_document_types`` mit ``include_count=true``):
beide gruppieren pro Owner über nicht-gelöschte Dokumente. Die partiellen
Composite-Indizes bedienen genau dieses Muster und schließen gelöschte Zeilen aus.

Revision ID: 062_document_count_indexes
Revises: 061_search_events
Create Date: 2026-07-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "062_document_count_indexes"
down_revision: Union[str, None] = "061_search_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVE_ONLY = sa.text("is_deleted = false")


def upgrade() -> None:
    op.create_index(
        "ix_documents_owner_type_active",
        "documents",
        ["owner_id", "document_type"],
        postgresql_where=_ACTIVE_ONLY,
    )
    op.create_index(
        "ix_documents_owner_correspondent_active",
        "documents",
        ["owner_id", "correspondent_id"],
        postgresql_where=_ACTIVE_ONLY,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_owner_correspondent_active", table_name="documents")
    op.drop_index("ix_documents_owner_type_active", table_name="documents")
