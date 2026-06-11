"""add profile fields to users (display_name, email, last_login_at)

Revision ID: 039_user_profile_fields
Revises: 038_embeddings_dim_1024
Create Date: 2026-06-07 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039_user_profile_fields"
down_revision: Union[str, None] = "038_embeddings_dim_1024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("email", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    # Case-insensitive uniqueness for e-mails, but only for rows that have one.
    op.execute(
        "CREATE UNIQUE INDEX ix_users_email_lower ON users (lower(email)) WHERE email IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_email_lower")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "email")
    op.drop_column("users", "display_name")
