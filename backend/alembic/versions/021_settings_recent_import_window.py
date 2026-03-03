"""add recent import window setting to global settings

Revision ID: 021_recent_import_window
Revises: 020_smart_folders
Create Date: 2026-03-01 19:20:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "021_recent_import_window"
down_revision: Union[str, None] = "020_smart_folders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = COALESCE(settings_json, '{}'::jsonb)
          || jsonb_build_object(
            'documents',
            jsonb_build_object(
              'recent_import_window_hours', 24
            ) || COALESCE(settings_json->'documents', '{}'::jsonb)
          )
        WHERE id = 1;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = settings_json
          || jsonb_build_object(
            'documents', COALESCE(settings_json->'documents', '{}'::jsonb)
              - 'recent_import_window_hours'
          )
        WHERE id = 1;
        """
    )
