"""Kontext des vollständigen Absatzes für Lern-Marker.

Revision ID: 100_learn_marker_context
Revises: 099_learn_runs
Create Date: 2026-09-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "100_learn_marker_context"
down_revision: Union[str, None] = "099_learn_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learn_marker",
        sa.Column("context", sa.Text(), nullable=False, server_default=""),
    )
    # Bestehende Marker stammen noch aus Ganzabsatz-Markierungen.
    op.execute("UPDATE learn_marker SET context = snippet WHERE context = ''")


def downgrade() -> None:
    op.drop_column("learn_marker", "context")
