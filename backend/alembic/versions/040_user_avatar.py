"""add avatar_key to users (profile picture)

Revision ID: 040_user_avatar
Revises: 039_user_profile_fields
Create Date: 2026-06-08 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040_user_avatar"
down_revision: Union[str, None] = "039_user_profile_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_key")
