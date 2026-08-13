"""apply the lean chat defaults to installations that still use the old defaults.

Die Änderung ist absichtlich konservativ: explizit vom Nutzer gesetzte Werte
bleiben unangetastet. Nur die ursprünglichen PaperMind-Defaults werden auf die
für den Pi angemessenen, kürzeren Live-Chat-Grenzen gestellt.

Revision ID: 065_chat_latency_defaults
Revises: 064_backup_source_state
Create Date: 2026-07-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "065_chat_latency_defaults"
down_revision: Union[str, None] = "064_backup_source_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = jsonb_set(
          jsonb_set(
            jsonb_set(settings_json, '{llm,max_output_tokens}', '420'::jsonb, true),
            '{rag,top_k}', '5'::jsonb, true
          ),
          '{rag,max_context_chars}', '6500'::jsonb, true
        )
        WHERE id = 1
          AND COALESCE(settings_json->'llm'->>'max_output_tokens', '1200') = '1200'
          AND COALESCE(settings_json->'rag'->>'top_k', '8') = '8'
          AND COALESCE(settings_json->'rag'->>'max_context_chars', '12000') = '12000';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = jsonb_set(
          jsonb_set(
            jsonb_set(settings_json, '{llm,max_output_tokens}', '1200'::jsonb, true),
            '{rag,top_k}', '8'::jsonb, true
          ),
          '{rag,max_context_chars}', '12000'::jsonb, true
        )
        WHERE id = 1
          AND settings_json->'llm'->>'max_output_tokens' = '420'
          AND settings_json->'rag'->>'top_k' = '5'
          AND settings_json->'rag'->>'max_context_chars' = '6500';
        """
    )
