"""add fixed areas to document types

Revision ID: 052_document_type_areas
Revises: 051_collection_kind
Create Date: 2026-06-23 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052_document_type_areas"
down_revision: Union[str, None] = "051_collection_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AREA_BY_NAME: dict[str, str] = {
    # Finanzen
    "Rechnung": "finance",
    "Mahnung": "finance",
    "Quittung": "finance",
    "Kontoauszug": "finance",
    "Kreditkartenabrechnung": "finance",
    "Bankbeleg": "finance",
    "Überweisungsbeleg": "finance",
    "Nebenkostenabrechnung": "finance",
    "Heizkostenabrechnung": "finance",
    "SEPA-Lastschriftmandat": "finance",
    "Werkstattrechnung": "finance",
    "Lieferschein": "finance",
    "Belege": "finance",
    "Bank": "finance",
    "Rechnungen": "finance",
    # Verträge & Recht
    "Vertrag": "contracts_law",
    "Kündigung": "contracts_law",
    "Mietvertrag": "contracts_law",
    "Kaufvertrag": "contracts_law",
    "Erbschein": "contracts_law",
    "Testament": "contracts_law",
    "Vollmacht": "contracts_law",
    "Datenschutzerklärung": "contracts_law",
    "AGB": "contracts_law",
    "Garantiebescheinigung": "contracts_law",
    "Gewährleistung": "contracts_law",
    "Reklamation": "contracts_law",
    "Mahnschreiben Anwalt": "contracts_law",
    "Pfändungsbeschluss": "contracts_law",
    "Gerichtsurteil": "contracts_law",
    "Beschluss": "contracts_law",
    "Verträge": "contracts_law",
    # Versicherungen
    "Beitragsrechnung": "insurance",
    "Police": "insurance",
    "Versicherungsnachweis": "insurance",
    "Sozialversicherungsausweis": "insurance",
    "Versicherung": "insurance",
    # Behörden & Steuern
    "Verwarnung": "government_tax",
    "Lohnsteuerbescheinigung": "government_tax",
    "Steuerbescheid": "government_tax",
    "Einkommensteuerbescheid": "government_tax",
    "Bescheid": "government_tax",
    "Antrag": "government_tax",
    "Urkunde Personenstand": "government_tax",
    "Personalausweis-Kopie": "government_tax",
    "Reisepass-Kopie": "government_tax",
    "Visum": "government_tax",
    "Meldebescheinigung": "government_tax",
    "Steuern": "government_tax",
    # Personal
    "Gehaltsabrechnung": "employment",
    "Arbeitsvertrag": "employment",
    "Ausbildungsvertrag": "employment",
    "Aufhebungsvertrag": "employment",
    "Zeugnis": "employment",
    "Zertifikat": "employment",
    "Klassenliste": "employment",
    "Teilnehmerliste": "employment",
    "Lebenslauf": "employment",
    "Bewerbung": "employment",
    "Schulbescheinigung": "employment",
    "Immatrikulationsbescheinigung": "employment",
    "Studienbescheinigung": "employment",
    # Gesundheit
    "Arbeitsunfähigkeitsbescheinigung": "health",
    "Impfpass": "health",
    "Impfnachweis": "health",
    "Arztbrief": "health",
    "Befund": "health",
    "Rezept": "health",
    # Zugang & IT
    "Aktivierungscode": "access_it",
    "Zugangsdaten": "access_it",
}


def upgrade() -> None:
    op.add_column("document_types", sa.Column("area", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_document_types_area",
        "document_types",
        "area IS NULL OR area IN "
        "('finance', 'contracts_law', 'insurance', 'government_tax', "
        "'employment', 'health', 'access_it', 'other')",
    )

    document_types = sa.table(
        "document_types",
        sa.column("name", sa.Text()),
        sa.column("area", sa.Text()),
    )
    bind = op.get_bind()
    for name, area in _AREA_BY_NAME.items():
        bind.execute(
            document_types.update()
            .where(sa.func.lower(document_types.c.name) == name.lower())
            .values(area=area)
        )

    # Bekannte Standardtypen ohne spezifischeren Bereich werden als Sonstiges
    # einsortiert. Benutzerdefinierte Typen bleiben bewusst unzugeordnet.
    standard_names = [
        "Bescheinigung", "Urkunde", "Auftrag", "Auftragsbestätigung", "Angebot",
        "Anmeldung", "Anmeldebestätigung", "Aufnahmebestätigung", "Bestätigung",
        "Anschreiben", "Brief", "Mitteilung", "Information", "Hinweis", "Einladung",
        "Zusage", "Absage", "Hauptuntersuchung", "TÜV-Bericht", "Niederschrift",
        "Protokoll", "Sonstiges", "Briefe",
    ]
    bind.execute(
        document_types.update()
        .where(sa.func.lower(document_types.c.name).in_([name.lower() for name in standard_names]))
        .values(area="other")
    )


def downgrade() -> None:
    op.drop_constraint("ck_document_types_area", "document_types", type_="check")
    op.drop_column("document_types", "area")
