"""rewrite document type naming templates to the CSV-derived house style

Betreff zuerst, Leerzeichen statt "–", kein Dokumenttyp im Namen, Datum-
Granularität je Dokumentart (volles Datum / Monat+Jahr / Jahr / keins).

Revision ID: 035_naming_templates_house_style
Revises: 034_correspondent_seed
Create Date: 2026-06-03 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035_naming_templates_house_style"
down_revision: Union[str, None] = "034_correspondent_seed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FULL = "{betreff} {datum:dd.MM.yyyy}"   # Ereignis: volles Datum (z. B. Rechnung 30.09.2013)
MONTH = "{betreff} {monat} {jahr}"      # monatlich (z. B. Ausbildungsvergütung Dezember 2014)
YEAR = "{betreff} {jahr}"               # jährlich (z. B. Einkommensteuerbescheid 2024)
PLAIN = "{betreff}"                     # zeitlos (z. B. Zertifikat Social Media)


_TEMPLATES: dict[str, str] = {
    # Rechnungen / Zahlungen
    "Rechnung": FULL,
    "Werkstattrechnung": FULL,
    "Beitragsrechnung": MONTH,
    "Gehaltsabrechnung": MONTH,
    "Kontoauszug": MONTH,
    "Kreditkartenabrechnung": MONTH,
    "Bankbeleg": FULL,
    "Überweisungsbeleg": FULL,
    "Quittung": FULL,
    "Mahnung": FULL,
    "Mahnschreiben Anwalt": FULL,
    "Verwarnung": FULL,
    # Verträge
    "Vertrag": FULL,
    "Arbeitsvertrag": FULL,
    "Ausbildungsvertrag": FULL,
    "Aufhebungsvertrag": FULL,
    "Kaufvertrag": FULL,
    "Mietvertrag": PLAIN,
    "Kündigung": FULL,
    # Versicherung / Vorsorge
    "Police": PLAIN,
    "Versicherungsnachweis": YEAR,
    # Bescheide / Steuer
    "Steuerbescheid": YEAR,
    "Einkommensteuerbescheid": YEAR,
    "Lohnsteuerbescheinigung": YEAR,
    "Bescheid": YEAR,
    # Bescheinigungen
    "Bescheinigung": FULL,
    "Arbeitsunfähigkeitsbescheinigung": FULL,
    "Schulbescheinigung": YEAR,
    "Immatrikulationsbescheinigung": YEAR,
    "Studienbescheinigung": YEAR,
    "Meldebescheinigung": MONTH,
    "Sozialversicherungsausweis": PLAIN,
    # Schriftverkehr
    "Anschreiben": FULL,
    "Brief": FULL,
    "Mitteilung": FULL,
    "Information": FULL,
    "Hinweis": FULL,
    "Einladung": FULL,
    "Zusage": FULL,
    "Absage": FULL,
    # Anträge / Aufträge / Bestätigungen
    "Antrag": FULL,
    "Auftrag": FULL,
    "Auftragsbestätigung": FULL,
    "Angebot": FULL,
    "Anmeldung": FULL,
    "Anmeldebestätigung": FULL,
    "Aufnahmebestätigung": FULL,
    "Bestätigung": FULL,
    # Zugänge / Codes
    "Aktivierungscode": FULL,
    "Zugangsdaten": FULL,
    # KFZ
    "Hauptuntersuchung": YEAR,
    "TÜV-Bericht": YEAR,
    # Listen / Protokolle
    "Klassenliste": PLAIN,
    "Teilnehmerliste": PLAIN,
    "Niederschrift": FULL,
    "Protokoll": FULL,
    "Lieferschein": FULL,
    # Bewerbung / Qualifikation
    "Lebenslauf": PLAIN,
    "Bewerbung": PLAIN,
    "Zeugnis": PLAIN,
    "Zertifikat": PLAIN,
    "Urkunde": PLAIN,
    # Wohnen
    "Nebenkostenabrechnung": YEAR,
    "Heizkostenabrechnung": YEAR,
    # Recht / Amt
    "Erbschein": FULL,
    "Testament": FULL,
    "Vollmacht": FULL,
    "SEPA-Lastschriftmandat": FULL,
    "Datenschutzerklärung": FULL,
    "AGB": PLAIN,
    "Garantiebescheinigung": FULL,
    "Gewährleistung": FULL,
    "Reklamation": FULL,
    "Pfändungsbeschluss": FULL,
    "Gerichtsurteil": FULL,
    "Beschluss": FULL,
    # Ausweise / Personenstand
    "Urkunde Personenstand": FULL,
    "Personalausweis-Kopie": PLAIN,
    "Reisepass-Kopie": PLAIN,
    "Visum": PLAIN,
    "Impfpass": PLAIN,
    "Impfnachweis": FULL,
    # Gesundheit
    "Arztbrief": FULL,
    "Befund": FULL,
    "Rezept": FULL,
    # Auffang
    "Sonstiges": FULL,
}


def upgrade() -> None:
    bind = op.get_bind()
    document_types = sa.table(
        "document_types",
        sa.column("name", sa.Text()),
        sa.column("naming_template", sa.Text()),
    )
    for name, template in _TEMPLATES.items():
        bind.execute(
            document_types.update()
            .where(sa.func.lower(document_types.c.name) == name.lower())
            .values(naming_template=template)
        )


def downgrade() -> None:
    # Reine Daten-Aktualisierung der Template-Strings. Beim Downgrade werden die
    # Templates geleert; sie fallen dann auf den Legacy-Builder zurück.
    bind = op.get_bind()
    document_types = sa.table(
        "document_types",
        sa.column("name", sa.Text()),
        sa.column("naming_template", sa.Text()),
    )
    for name in _TEMPLATES:
        bind.execute(
            document_types.update()
            .where(sa.func.lower(document_types.c.name) == name.lower())
            .values(naming_template=None)
        )
