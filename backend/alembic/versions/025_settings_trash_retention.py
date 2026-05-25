"""settings: trash retention days

Revision ID: 025_settings_trash_retention
Revises: 024_documents_trash_favorite
Create Date: 2026-05-25
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "025_settings_trash_retention"
down_revision: Union[str, None] = "024_documents_trash_favorite"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE global_settings
            SET settings_json = COALESCE(settings_json, '{}'::jsonb)
              || jsonb_build_object(
                'documents',
                jsonb_build_object('trash_retention_days', 30)
                  || COALESCE(settings_json->'documents', '{}'::jsonb)
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE global_settings
            SET settings_json = COALESCE(settings_json, '{}'::jsonb)
              || jsonb_build_object(
                'documents',
                COALESCE(settings_json->'documents', '{}'::jsonb) - 'trash_retention_days'
              )
            """
        )
    )
