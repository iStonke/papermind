"""Count job attempts and record why a job was ended automatically."""
from alembic import op
import sqlalchemy as sa
revision = "106_job_attempts"
down_revision = "105_thought_rooms"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("jobs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    # timeout | retry_limit | cancelled – NULL bei gewöhnlichen Fehlern.
    op.add_column("jobs", sa.Column("failure_kind", sa.String(32), nullable=True))

def downgrade():
    op.drop_column("jobs", "failure_kind")
    op.drop_column("jobs", "attempts")
