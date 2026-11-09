"""Vor- und Nachnamen für Personen speichern.

Revision ID: 118_correspondent_person_names
Revises: 117_correspondent_collections
"""

import sqlalchemy as sa
from alembic import op

revision = "118_correspondent_person_names"
down_revision = "117_correspondent_collections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("correspondents", sa.Column("first_name", sa.Text(), nullable=True))
    op.add_column("correspondents", sa.Column("last_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("correspondents", "last_name")
    op.drop_column("correspondents", "first_name")
