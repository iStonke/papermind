"""allow collection correspondents

Revision ID: 051_collection_kind
Revises: 050_correspondent_type_hierarchy
Create Date: 2026-06-22 22:30:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "051_collection_kind"
down_revision: Union[str, None] = "050_correspondent_type_hierarchy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_correspondents_kind", "correspondents", type_="check")
    op.create_check_constraint(
        "ck_correspondents_kind",
        "correspondents",
        "kind IS NULL OR kind IN ('organization', 'person', 'collection')",
    )


def downgrade() -> None:
    # Ein Downgrade ist nur möglich, wenn keine Sammelkorrespondenten mehr
    # existieren; PostgreSQL prüft das beim Anlegen des engeren Constraints.
    op.drop_constraint("ck_correspondents_kind", "correspondents", type_="check")
    op.create_check_constraint(
        "ck_correspondents_kind",
        "correspondents",
        "kind IS NULL OR kind IN ('organization', 'person')",
    )
