"""per-scanner live page mode.

Übernimmt den bisher globalen Wert documents.scan_live_page_mode einmalig auf
alle vorhandenen Scanner (scanner_devices.live_page_mode) und entfernt den
globalen Schlüssel aus den Einstellungen. „Seiten sofort senden" ist ab jetzt
ausschließlich pro Scanner konfiguriert.

Revision ID: 080_per_scanner_live_page_mode
Revises: 079_shared_scanner_inbox
Create Date: 2026-08-21 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "080_per_scanner_live_page_mode"
down_revision: Union[str, None] = "079_shared_scanner_inbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Globalen Wert auf alle Scanner übernehmen (Default false, wenn nicht gesetzt).
    op.execute(
        """
        UPDATE scanner_devices
        SET live_page_mode = COALESCE(
            (
                SELECT (settings_json #>> '{documents,scan_live_page_mode}')::boolean
                FROM global_settings
                WHERE id = 1
            ),
            false
        )
        """
    )
    # Globalen Schlüssel entfernen - er wird nicht mehr gelesen.
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = settings_json #- '{documents,scan_live_page_mode}'
        WHERE id = 1
        """
    )


def downgrade() -> None:
    # Globalen Schlüssel aus dem (früheren) Wert eines Scanners rekonstruieren.
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = jsonb_set(
            settings_json,
            '{documents,scan_live_page_mode}',
            to_jsonb(COALESCE(
                (SELECT bool_or(live_page_mode) FROM scanner_devices),
                false
            )),
            true
        )
        WHERE id = 1
        """
    )
