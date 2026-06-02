"""add document type metadata and AP10 seed values

Revision ID: 032_document_type_metadata_seed
Revises: 031_document_types_rename
Create Date: 2026-06-02 00:00:00.000000
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "032_document_type_metadata_seed"
down_revision: Union[str, None] = "031_document_types_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DOCUMENT_TYPE_SEED: list[dict[str, object]] = [
    {
        "name": "Rechnung",
        "naming_template": "Rechnung – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}[ – {betrag}]",
        "prompt_hint": "Rechnung, Invoice, Forderung mit Gesamtbetrag oder Rechnungsnummer.",
    },
    {
        "name": "Beitragsrechnung",
        "naming_template": "Beitragsrechnung – {korrespondent} – {sparte} – {monat} {jahr}",
        "prompt_hint": "Regelmäßige Beitragsforderung, häufig Versicherung, Verein oder Versorgung.",
    },
    {"name": "Gehaltsabrechnung", "naming_template": "Gehaltsabrechnung – {korrespondent} – {monat} {jahr}"},
    {"name": "Mahnung", "naming_template": "Mahnung – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Verwarnung", "naming_template": "Verwarnung – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Quittung", "naming_template": "Quittung – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}[ – {betrag}]"},
    {"name": "Vertrag", "naming_template": "Vertrag – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Arbeitsvertrag", "naming_template": "Arbeitsvertrag – {korrespondent} – {datum:dd.MM.yyyy}"},
    {"name": "Ausbildungsvertrag", "naming_template": "Ausbildungsvertrag – {korrespondent} – {datum:dd.MM.yyyy}"},
    {"name": "Aufhebungsvertrag", "naming_template": "Aufhebungsvertrag – {korrespondent} – {datum:dd.MM.yyyy}"},
    {"name": "Kündigung", "naming_template": "Kündigung – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Police", "naming_template": "Police – {korrespondent} – {sparte} – {police_nr}"},
    {"name": "Versicherungsnachweis", "naming_template": "Versicherungsnachweis – {korrespondent} – {sparte} – {jahr}"},
    {"name": "Bescheinigung", "naming_template": "Bescheinigung – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {
        "name": "Arbeitsunfähigkeitsbescheinigung",
        "naming_template": "AU-Bescheinigung – {arzt_oder_korrespondent} – {datum:dd.MM.yyyy}",
    },
    {"name": "Lohnsteuerbescheinigung", "naming_template": "Lohnsteuerbescheinigung – {korrespondent} – {jahr}"},
    {"name": "Steuerbescheid", "naming_template": "Steuerbescheid – {korrespondent} – {steuerjahr}"},
    {"name": "Einkommensteuerbescheid", "naming_template": "Einkommensteuerbescheid – Finanzamt – {steuerjahr}"},
    {"name": "Bescheid", "naming_template": "{bescheidart} – {korrespondent} – {steuerjahr|datum:dd.MM.yyyy}"},
    {"name": "Zeugnis", "naming_template": "{zeugnisart} – {schule} – {schuljahr}"},
    {"name": "Zertifikat", "naming_template": "Zertifikat – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Urkunde", "naming_template": "Urkunde – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Antrag", "naming_template": "Antrag – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Auftrag", "naming_template": "Auftrag – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Auftragsbestätigung", "naming_template": "Auftragsbestätigung – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Angebot", "naming_template": "Angebot – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Anmeldung", "naming_template": "Anmeldung – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Anmeldebestätigung", "naming_template": "Anmeldebestätigung – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Aufnahmebestätigung", "naming_template": "Aufnahmebestätigung – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Bestätigung", "naming_template": "Bestätigung – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Anschreiben", "naming_template": "Anschreiben – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Brief", "naming_template": "Brief – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Mitteilung", "naming_template": "Mitteilung – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Information", "naming_template": "Information – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Hinweis", "naming_template": "Hinweis – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Einladung", "naming_template": "Einladung – {korrespondent} – {anlass} – {datum:dd.MM.yyyy}"},
    {"name": "Zusage", "naming_template": "Zusage – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Absage", "naming_template": "Absage – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Aktivierungscode", "naming_template": "Aktivierungscode – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Zugangsdaten", "naming_template": "Zugangsdaten – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Hauptuntersuchung", "naming_template": "Hauptuntersuchung – {kennzeichen|fahrzeug} – {jahr}"},
    {"name": "TÜV-Bericht", "naming_template": "TÜV-Bericht – {kennzeichen|fahrzeug} – {jahr}"},
    {"name": "Klassenliste", "naming_template": "Klassenliste – {schule} – {schuljahr}"},
    {"name": "Teilnehmerliste", "naming_template": "Teilnehmerliste – {korrespondent} – {anlass} – {datum:dd.MM.yyyy}"},
    {"name": "Niederschrift", "naming_template": "Niederschrift – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Protokoll", "naming_template": "Protokoll – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Lieferschein", "naming_template": "Lieferschein – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Lebenslauf", "naming_template": "Lebenslauf – {person} – {datum:dd.MM.yyyy}"},
    {"name": "Bewerbung", "naming_template": "Bewerbung – {person} – {stelle} – {datum:dd.MM.yyyy}"},
    {"name": "Kontoauszug", "naming_template": "Kontoauszug – {bank} – {iban:last4} – {jahr}-{monat:02d}"},
    {"name": "Kreditkartenabrechnung", "naming_template": "Kreditkartenabrechnung – {bank} – {jahr}-{monat:02d}"},
    {"name": "Bankbeleg", "naming_template": "Bankbeleg – {bank} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Überweisungsbeleg", "naming_template": "Überweisungsbeleg – {bank} – {empfänger} – {datum:dd.MM.yyyy}"},
    {"name": "Mietvertrag", "naming_template": "Mietvertrag – {korrespondent} – {objekt} – {datum:dd.MM.yyyy}"},
    {"name": "Nebenkostenabrechnung", "naming_template": "Nebenkostenabrechnung – {korrespondent} – Abrechnungsjahr {jahr}"},
    {"name": "Heizkostenabrechnung", "naming_template": "Heizkostenabrechnung – {korrespondent} – Abrechnungsjahr {jahr}"},
    {"name": "Erbschein", "naming_template": "Erbschein – {person} – {datum:dd.MM.yyyy}"},
    {"name": "Testament", "naming_template": "Testament – {person} – {datum:dd.MM.yyyy}"},
    {"name": "Vollmacht", "naming_template": "Vollmacht – {person} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "SEPA-Lastschriftmandat", "naming_template": "SEPA-Lastschriftmandat – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Datenschutzerklärung", "naming_template": "Datenschutzerklärung – {korrespondent} – {datum:dd.MM.yyyy}"},
    {"name": "AGB", "naming_template": "AGB – {korrespondent} – {datum:dd.MM.yyyy}"},
    {"name": "Garantiebescheinigung", "naming_template": "Garantiebescheinigung – {korrespondent} – {produkt} – {datum:dd.MM.yyyy}"},
    {"name": "Gewährleistung", "naming_template": "Gewährleistung – {korrespondent} – {produkt} – {datum:dd.MM.yyyy}"},
    {"name": "Reklamation", "naming_template": "Reklamation – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Urkunde Personenstand", "naming_template": "{urkundenart} – {person} – {datum:dd.MM.yyyy}"},
    {"name": "Personalausweis-Kopie", "naming_template": "Personalausweis-Kopie – {person} – {datum:dd.MM.yyyy}"},
    {"name": "Reisepass-Kopie", "naming_template": "Reisepass-Kopie – {person} – {datum:dd.MM.yyyy}"},
    {"name": "Visum", "naming_template": "Visum – {land} – {person} – {datum:dd.MM.yyyy}"},
    {"name": "Impfpass", "naming_template": "Impfpass – {person} – {datum:dd.MM.yyyy}"},
    {"name": "Impfnachweis", "naming_template": "Impfnachweis – {person} – {impfung} – {datum:dd.MM.yyyy}"},
    {"name": "Arztbrief", "naming_template": "Arztbrief – {arzt_oder_korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Befund", "naming_template": "Befund – {arzt_oder_korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Rezept", "naming_template": "Rezept – {arzt_oder_korrespondent} – {datum:dd.MM.yyyy}"},
    {"name": "Mahnschreiben Anwalt", "naming_template": "Mahnschreiben Anwalt – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Pfändungsbeschluss", "naming_template": "Pfändungsbeschluss – {korrespondent} – {datum:dd.MM.yyyy}"},
    {"name": "Gerichtsurteil", "naming_template": "Gerichtsurteil – {korrespondent} – {aktenzeichen} – {datum:dd.MM.yyyy}"},
    {"name": "Beschluss", "naming_template": "Beschluss – {korrespondent} – {aktenzeichen|betreff:short} – {datum:dd.MM.yyyy}"},
    {"name": "Schulbescheinigung", "naming_template": "Schulbescheinigung – {schule} – {schuljahr}"},
    {"name": "Immatrikulationsbescheinigung", "naming_template": "Immatrikulationsbescheinigung – {hochschule} – {semester}"},
    {"name": "Studienbescheinigung", "naming_template": "Studienbescheinigung – {hochschule} – {semester}"},
    {"name": "Sozialversicherungsausweis", "naming_template": "Sozialversicherungsausweis – {person}"},
    {"name": "Meldebescheinigung", "naming_template": "Meldebescheinigung – {person} – {datum:dd.MM.yyyy}"},
    {"name": "Werkstattrechnung", "naming_template": "Werkstattrechnung – {korrespondent} – {fahrzeug} – {datum:dd.MM.yyyy}[ – {betrag}]"},
    {"name": "Kaufvertrag", "naming_template": "Kaufvertrag – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"},
    {"name": "Sonstiges", "naming_template": "Dokument – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"},
]

_LEGACY_NAMES = ["Bank", "Belege", "Briefe", "Rechnungen", "Steuern", "Versicherung", "Verträge"]


def upgrade() -> None:
    op.add_column("document_types", sa.Column("naming_template", sa.Text(), nullable=True))
    op.add_column("document_types", sa.Column("prompt_hint", sa.Text(), nullable=True))
    op.add_column("document_types", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("document_types", sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False))

    bind = op.get_bind()
    document_types_table = sa.table(
        "document_types",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.Text()),
        sa.column("naming_template", sa.Text()),
        sa.column("prompt_hint", sa.Text()),
        sa.column("is_active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
    )

    for idx, seed in enumerate(_DOCUMENT_TYPE_SEED, start=10):
        existing = bind.execute(
            sa.select(document_types_table.c.name).where(sa.func.lower(document_types_table.c.name) == str(seed["name"]).lower())
        ).scalar_one_or_none()
        values = {
            "naming_template": seed.get("naming_template"),
            "prompt_hint": seed.get("prompt_hint"),
            "is_active": True,
            "sort_order": idx,
        }
        if existing:
            bind.execute(
                document_types_table.update()
                .where(sa.func.lower(document_types_table.c.name) == str(seed["name"]).lower())
                .values(**values)
            )
        else:
            bind.execute(
                document_types_table.insert().values(
                    id=uuid.uuid4(),
                    name=seed["name"],
                    **values,
                )
            )

    documents_table = sa.table(
        "documents",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("document_type", sa.Text()),
        sa.column("is_deleted", sa.Boolean()),
    )
    for name in _LEGACY_NAMES:
        usage_count = bind.execute(
            sa.select(sa.func.count())
            .select_from(documents_table)
            .where(documents_table.c.document_type == name)
        ).scalar_one()
        bind.execute(
            document_types_table.update()
            .where(document_types_table.c.name == name)
            .values(
                prompt_hint="Legacy-Wert aus der früheren Kategorienliste.",
                is_active=usage_count > 0,
                sort_order=9000,
            )
        )


def downgrade() -> None:
    document_types_table = sa.table("document_types", sa.column("name", sa.Text()))
    op.execute(
        document_types_table.delete().where(
            document_types_table.c.name.in_([str(seed["name"]) for seed in _DOCUMENT_TYPE_SEED])
        )
    )
    op.drop_column("document_types", "sort_order")
    op.drop_column("document_types", "is_active")
    op.drop_column("document_types", "prompt_hint")
    op.drop_column("document_types", "naming_template")
