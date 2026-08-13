"""align configurable chunking with the production retrieval defaults.

Revision ID: 076_chat_retrieval_defaults
Revises: 075_wiki_backfill_controls
Create Date: 2026-08-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "076_chat_retrieval_defaults"
down_revision: Union[str, None] = "075_wiki_backfill_controls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = jsonb_set(
          jsonb_set(settings_json, '{rag,chunk_chars}', '1000'::jsonb, true),
          '{rag,chunk_overlap_chars}', '100'::jsonb, true
        )
        WHERE id = 1
          AND COALESCE(settings_json->'rag'->>'chunk_chars', '4500') = '4500'
          AND COALESCE(settings_json->'rag'->>'chunk_overlap_chars', '600') = '600';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = jsonb_set(
          jsonb_set(settings_json, '{rag,chunk_chars}', '4500'::jsonb, true),
          '{rag,chunk_overlap_chars}', '600'::jsonb, true
        )
        WHERE id = 1
          AND settings_json->'rag'->>'chunk_chars' = '1000'
          AND settings_json->'rag'->>'chunk_overlap_chars' = '100';
        """
    )
