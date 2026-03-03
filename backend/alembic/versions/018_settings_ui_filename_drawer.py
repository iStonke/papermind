"""extend global settings with filename and drawer ui toggles

Revision ID: 018_settings_ui_filename_drawer
Revises: 017_document_date_ssot
Create Date: 2026-02-28 21:30:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "018_settings_ui_filename_drawer"
down_revision: Union[str, None] = "017_document_date_ssot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = COALESCE(settings_json, '{}'::jsonb)
          || jsonb_build_object(
            'ui',
            jsonb_build_object(
              'theme_mode', 'system',
              'showFilenameSuffix', true,
              'drawerRememberState', true,
              'drawerAlwaysExpanded', false
            ) || COALESCE(settings_json->'ui', '{}'::jsonb),
            'documents',
            jsonb_build_object(
              'auto_ocr', true,
              'auto_tagging', false,
              'sort_order', 'newest'
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
            'ui', COALESCE(settings_json->'ui', '{}'::jsonb)
              - 'showFilenameSuffix'
              - 'drawerRememberState'
              - 'drawerAlwaysExpanded'
          )
        WHERE id = 1;
        """
    )
