"""Turn off unpaper in the OCR confidence pass for existing installations.

unpaper wirkt nur auf den zweiten Seitendurchlauf, der die OCR-Konfidenz
bestimmt; ocrmypdf bereinigt unabhängig davon. Gemessen an 21 Dokumenten
brachte es keinen Nutzen, kostete aber rund die Hälfte dieses Durchlaufs und
erzeugte Fehlwarnungen. Die Oberfläche bietet keinen Schalter dafür, ein
gespeichertes ``true`` ist also immer der alte Default.
"""
from alembic import op
revision = "107_ocr_unpaper_off"
down_revision = "106_job_attempts"
branch_labels = None
depends_on = None

def upgrade():
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = jsonb_set(settings_json, '{ocr,use_unpaper}', 'false'::jsonb, true)
        WHERE id = 1 AND settings_json->'ocr'->>'use_unpaper' = 'true';
        """
    )

def downgrade():
    op.execute(
        """
        UPDATE global_settings
        SET settings_json = jsonb_set(settings_json, '{ocr,use_unpaper}', 'true'::jsonb, true)
        WHERE id = 1 AND settings_json->'ocr'->>'use_unpaper' = 'false';
        """
    )
