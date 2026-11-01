"""Store manual corrections separately from AI recognition results."""
from alembic import op
import sqlalchemy as sa

revision = "115_knowledge_corrections"
down_revision = "114_import_receipts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("recipient", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("documents", sa.Column("currency", sa.String(3), nullable=True))


def downgrade():
    for name in ("currency", "amount", "recipient"):
        op.drop_column("documents", name)
