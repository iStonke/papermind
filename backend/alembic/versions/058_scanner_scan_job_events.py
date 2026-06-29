"""scanner scan job error kind and command linkage.

Revision ID: 058_scanner_scan_job_events
Revises: 057_scanner_scan_jobs
Create Date: 2026-06-28 12:00:00.000000

Ergänzt den Scan-Job-Lifecycle um zwei Dinge:

* ``scanner_scan_jobs.error_kind`` – strukturierte Fehlerart (timeout,
  file_missing, scanner_offline, failed), damit die UI gezielt erklären kann,
  WAS schiefgelaufen ist, statt nur eine rohe Fehlermeldung zu zeigen.
* ``scanner_scan_commands.scan_job_id`` – verknüpft einen eingereihten
  Hardware-Befehl mit genau dem Job, der ihn ausgelöst hat. So lässt sich ein
  abgelaufener Befehl (Host-Poller offline) dem richtigen Job als
  ``scanner_offline`` zuordnen, und der vom Host produzierte Scan kann später
  exakt diesem Job zugeordnet werden (Job-ID im Befehl/Dateinamen).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "058_scanner_scan_job_events"
down_revision: Union[str, None] = "057_scanner_scan_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scanner_scan_jobs",
        sa.Column("error_kind", sa.Text(), nullable=True),
    )
    op.add_column(
        "scanner_scan_commands",
        sa.Column(
            "scan_job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scanner_scan_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_scanner_scan_commands_scan_job_id",
        "scanner_scan_commands",
        ["scan_job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_scanner_scan_commands_scan_job_id", table_name="scanner_scan_commands")
    op.drop_column("scanner_scan_commands", "scan_job_id")
    op.drop_column("scanner_scan_jobs", "error_kind")
