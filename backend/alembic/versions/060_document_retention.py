"""separate document retention metadata.

Revision ID: 060_document_retention
Revises: 059_document_annotations
Create Date: 2026-06-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "060_document_retention"
down_revision: Union[str, None] = "059_document_annotations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OWNER_EXPR = "NULLIF(current_setting('app.owner_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "document_retention",
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), server_default=sa.text("'not_evaluated'"), nullable=False),
        sa.Column("period_years", sa.Integer(), nullable=True),
        sa.Column("retain_until", sa.Date(), nullable=True),
        sa.Column("paper_original", sa.String(length=24), server_default=sa.text("'unclear'"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('not_evaluated', 'suggested', 'accepted', 'manual')",
            name="ck_document_retention_status",
        ),
        sa.CheckConstraint(
            "paper_original IN ('unclear', 'keep', 'scan_sufficient', 'not_applicable')",
            name="ck_document_retention_paper_original",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
    )

    cond = (
        f"EXISTS (SELECT 1 FROM documents d "
        f"WHERE d.id = document_retention.document_id AND d.owner_id = {_OWNER_EXPR})"
    )
    op.execute("ALTER TABLE document_retention ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS document_retention_owner_isolation ON document_retention")
    op.execute(
        f"CREATE POLICY document_retention_owner_isolation ON document_retention "
        f"USING ({cond}) WITH CHECK ({cond})"
    )

    for role in ("papermind_app", "papermind_worker"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON document_retention TO "{role}";
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS document_retention_owner_isolation ON document_retention")
    op.drop_table("document_retention")
