# AP10 – Korrespondent, Dokumenttyp und konsistente KI-Namensvorschläge

Status: Konzept
Quelle: Auswertung `dateiliste.csv` (522 historisch getaggte Dokumente)
Bezug zu bestehenden APs: ergänzt AP6 (Tags), AP7 (Smart Folders), AP8/AP9 (KI), Naming im Import-Stage-Flow (`import_staging.suggest_stage_title` / `_build_filename_from_meta`)

## Ausgangslage

Im Bestand sind 522 Dokumente konsistent gepflegt: 506 mit mindestens einem Tag, 16 ohne. 34 eindeutige Tags, klar long-tail (Top 10 ≈ 75 %). Die meisten "Tags" sind in Wahrheit Absender/Aussteller (Dataport, Vodafone, HUK-Coburg, Krankenkasse, Hausverwaltung, Finanzamt Kiel, Landeshauptstadt Kiel, IHK SH, Schulen, …). Ein kleinerer Teil sind Sachgebiete (Gesundheit, Altersvorsorge, Kraftfahrzeug, Rechnung, Briefe).

Bereits umgesetzt:

- Kategorie als eigene Tabelle (`categories`) plus `Document.category` (denormalisiert).
- Dokumentdatum als `Document.document_date` inkl. Quelle und Konfidenz.
- KI-Klassifikator schreibt `ai_document_type`, `ai_sender`, `ai_recipient`, `ai_summary`, `ai_suggested_tags`, `ai_confidence`.
- Dateinamen-Generator `_build_filename_from_meta` mit Schema `Typ – Aussteller – Betreff [– Betrag€]`.

Lücken, die dieses AP schließt:

1. "Kategorie" ist generisch und kollidiert begrifflich mit "Dokumenttyp". Umbenennen.
2. Die Liste der erlaubten Dokumenttypen ist im Ollama-Prompt auf fünf Werte verkürzt (`Rechnung|Vertrag|Brief|Kontoauszug|Sonstiges`). Der Bestand braucht ein realistisches Vokabular.
3. Korrespondent existiert nur als freier String (`ai_sender`). Ohne Normalisierung/Aliase entstehen Dubletten und schlechte Vorschläge.
4. KI-Namensvorschläge sind aktuell pro-Dokument generisch; konsistente Benennung gleichartiger Dokumente (z. B. „Ausbildungsvergütung Dezember 2014") ist nicht garantiert.

## Ziele

- Hauptziel: Die KI schlägt für ähnliche Dokumente konsistente, vorhersehbare Dateinamen vor.
- Dokumenttypen werden als verwaltbares Vokabular geführt und decken den real existierenden Bestand ab.
- Korrespondenten werden als eigene Entität geführt, mit Aliasen und Matching-Regeln.
- Kein Bruch bestehender Daten: Migrationspfad ohne Datenverlust.

## Begriffe (Modell-Sicht)

- `Document.category` → in `Document.document_type` umbenennen, gleichbedeutend mit dem ausgewählten Dokumenttyp. Die Spalte bleibt denormalisiert (String), Quelle der Wahrheit ist die Tabelle `document_types`.
- Neue Tabelle `document_types` (ersetzt `categories`): verwaltbares Vokabular, in Settings pflegbar.
- Neue Tabelle `correspondents`: kanonischer Name + Aliase + Matching-Regeln.
- `Document.correspondent_id` als FK (nullable). `ai_sender` bleibt als roher LLM-Befund erhalten, wird beim Akzeptieren des Vorschlags auf den FK abgebildet.

## Vorgeschlagene Dokumenttypen-Liste

Abgeleitet aus den 522 Dateinamen, plus typische Lücken. Hierarchisch optional, in Phase 1 flach genügt.

Bestand-getrieben (≥ 3 Vorkommen):

- Rechnung
- Beitragsrechnung
- Gehaltsabrechnung
- Mahnung
- Verwarnung
- Quittung
- Vertrag
- Arbeitsvertrag
- Ausbildungsvertrag
- Aufhebungsvertrag
- Kündigung
- Police / Versicherungsschein
- Versicherungsnachweis
- Bescheinigung (generisch)
- Arbeitsunfähigkeitsbescheinigung
- Lohnsteuerbescheinigung
- Steuerbescheid / Einkommensteuerbescheid
- Bescheid (generisch)
- Zeugnis (Grundschul-, Realschul-, Berufsschul-, Halbjahres-, Jahres-, Abschluss-)
- Zertifikat / Urkunde
- Antrag
- Auftrag
- Auftragsbestätigung
- Angebot
- Anmeldung / Anmeldebestätigung
- Aufnahmebestätigung
- Bestätigung (generisch)
- Anschreiben / Brief
- Mitteilung / Information / Hinweis
- Einladung
- Zusage
- Absage
- Aktivierungscode / Zugangsdaten
- Hauptuntersuchung / TÜV-Bericht
- Klassenliste / Teilnehmerliste
- Niederschrift / Protokoll
- Lieferschein
- Lebenslauf
- Bewerbung

Sinnvolle Ergänzungen, die der Bestand nicht zeigt, aber im Alltag vorkommen:

- Kontoauszug
- Kreditkartenabrechnung
- Bankbeleg / Überweisungsbeleg
- Mietvertrag
- Nebenkostenabrechnung
- Heizkostenabrechnung
- Erbschein / Testament
- Vollmacht
- SEPA-Lastschriftmandat
- Datenschutzerklärung / AGB
- Garantiebescheinigung / Gewährleistung
- Reklamation
- Geburtsurkunde / Heiratsurkunde / Sterbeurkunde / Personalausweis-Kopie
- Reisepass-Kopie / Visum
- Impfpass / Impfnachweis
- Arztbrief / Befund / Rezept
- Mahnschreiben Anwalt
- Pfändungsbeschluss
- Gerichtsurteil / Beschluss
- Schulbescheinigung / Immatrikulationsbescheinigung / Studienbescheinigung
- Sozialversicherungsausweis / Meldebescheinigung
- Werkstattrechnung / TÜV-Bericht
- Kaufvertrag / Lieferschein / Garantie

In Phase 1 als statisches Seed in `document_types` einspielen, danach durch den Nutzer pflegbar.

## Korrespondenten – Modell und Initial-Seed

Schema (Vorschlag):

```text
correspondents
  id            uuid pk
  name          text  (kanonisch, unique)
  short_name    text  (für Dateinamen, z. B. "HUK")
  notes         text
  created_at    timestamptz

correspondent_aliases
  id              uuid pk
  correspondent_id uuid fk
  alias           text  (case-insensitive unique je correspondent)

correspondent_matchers
  id              uuid pk
  correspondent_id uuid fk
  kind            text  ('contains' | 'regex' | 'starts_with')
  pattern         text
  scope           text  ('filename' | 'ocr_text' | 'both')
  priority        int
```

Initial-Seed aus dem Bestand (CSV-Tag → Korrespondent + Alias + Matcher):

| Kanonisch              | short_name | Aliase / Matcher (Auszug)                                              |
| ---------------------- | ---------- | ---------------------------------------------------------------------- |
| Dataport AöR           | Dataport   | "Dataport"                                                             |
| Vodafone GmbH          | Vodafone   | "Vodafone", "Red Plus", "GigaKombi"                                    |
| HUK-Coburg             | HUK        | "HUK", "HUK-Coburg", "Privathaftpflicht", "Beitragsrechnung Kfz"       |
| Finanzamt Kiel         | FA Kiel    | "Finanzamt", "ELSTER", "Einkommensteuerbescheid", "Lohnsteuer"         |
| Landeshauptstadt Kiel  | LH Kiel    | "Landeshauptstadt Kiel"                                                |
| Hausverwaltung         | HV         | "Hausverwaltung", "SEPA-Lastschrift", "Nebenkostenabrechnung"          |
| Techem                 | Techem     | "Techem", "Heizkosten"                                                 |
| Naturstrom AG          | Naturstrom | "Naturstrom"                                                           |
| SW Kiel Netz GmbH      | SW Kiel    | "SW Kiel", "Stadtwerke Kiel"                                           |
| Krankenkasse           | KK         | Pflicht-Frage: konkrete KK angeben; Default "Krankenkasse"             |
| Deutsche Rentenvers.   | DRV        | "Deutsche Rentenversicherung", "DRV"                                   |
| VBL                    | VBL        | "VBL"                                                                  |
| IHK Schleswig-Holstein | IHK SH     | "IHK Schleswig-Holstein", "IHK SH"                                     |
| RBZ Wirtschaft Kiel    | RBZ Kiel   | "RBZ Wirtschaft Kiel"                                                  |
| TH Lübeck              | TH HL      | "TH Lübeck", "FH Lübeck"                                               |
| Regionalschule Altenh. | RS Altenh. | "Regionalschule Altenholz"                                             |
| Timm-Kröger-Realschule | TKR        | "Timm-Kröger"                                                          |
| Reventlouschule Kiel   | Reventlou  | "Reventlouschule"                                                      |
| Baltic Drive           | Baltic     | "Baltic Drive", "Heinzi's Fahrschule"                                  |
| KMTV                   | KMTV       | "KMTV"                                                                 |
| Kieser Training        | Kieser     | "Kieser"                                                               |
| McFIT                  | McFIT      | "McFIT"                                                                |
| Tanzschule Gemind      | Gemind     | "Tanzschule Gemind"                                                    |
| mStore Kiel            | mStore     | "mStore"                                                               |

Hinweis: "Krankenkasse" und "Gesundheit" sind im Altbestand vermischt. Beim Migrieren: "Gesundheit" wird zum Sachgebiet (Tag bleibt), "Krankenkasse" wird zur Pflicht-Klärung beim Import (welche konkret).

## Kern: konsistente Namensvorschläge

Das aktuelle Schema im Filename-Builder ist gut, aber die Komponente `subject` ist frei und damit der Hauptgrund für Inkonsistenzen. Vorschlag: pro Dokumenttyp und optional pro (Dokumenttyp × Korrespondent) ein **Naming-Template** mit deterministischen Platzhaltern. Die KI bekommt das Template als harte Vorgabe – nicht als Beispiel.

### Naming-Templates (Beispiele)

Globale Defaults:

```text
Rechnung           → "Rechnung – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}[ – {betrag}]"
Beitragsrechnung   → "Beitragsrechnung – {korrespondent} – {sparte} – {monat} {jahr}"
Mahnung            → "Mahnung – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"
Gehaltsabrechnung  → "Gehaltsabrechnung – {korrespondent} – {monat} {jahr}"
Arbeitsunfähigkeitsbescheinigung → "AU-Bescheinigung – {arzt_oder_korrespondent} – {datum:dd.MM.yyyy}"
Vertrag            → "Vertrag – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"
Police             → "Police – {korrespondent} – {sparte} – {police_nr}"
Zeugnis            → "{zeugnisart} – {schule} – {schuljahr}"
Bescheinigung      → "Bescheinigung – {korrespondent} – {gegenstand} – {datum:dd.MM.yyyy}"
Bescheid           → "{bescheidart} – {korrespondent} – {steuerjahr|datum:dd.MM.yyyy}"
Lohnsteuerbescheinigung → "Lohnsteuerbescheinigung – {korrespondent} – {jahr}"
Einkommensteuerbescheid → "Einkommensteuerbescheid – Finanzamt – {steuerjahr}"
Hauptuntersuchung  → "Hauptuntersuchung – {kennzeichen|fahrzeug} – {jahr}"
Kontoauszug        → "Kontoauszug – {bank} – {iban:last4} – {jahr}-{monat:02d}"
Brief              → "Brief – {korrespondent} – {betreff:short} – {datum:dd.MM.yyyy}"
```

Korrespondenten-spezifische Overrides (Beispiel):

```text
Vodafone × Rechnung        → "Rechnung – Vodafone – {mobilfunknr} – {monat} {jahr}"
HUK-Coburg × Beitragsrechnung → "Beitragsrechnung – HUK – {sparte} – {monat} {jahr}"
Techem × Nebenkostenabrechnung → "Nebenkostenabrechnung – Techem – Abrechnungsjahr {jahr}"
```

Templates werden in `document_types.naming_template` und optional `correspondent_naming_overrides(type_id, correspondent_id, template)` gepflegt. Die Templates sind Daten, nicht Code: der Nutzer kann sie in Settings ändern.

### Pipeline für den Namensvorschlag

1. LLM klassifiziert Dokumenttyp und liefert Felder (date, sender, recipient, amount, subject, plus typ-spezifische Felder – siehe nächster Abschnitt).
2. `sender` wird gegen `correspondent_matchers` und `correspondent_aliases` aufgelöst. Treffer → kanonischer Korrespondent + `short_name`. Kein Treffer → unaufgelöster Vorschlag, der beim Akzeptieren angelegt werden kann.
3. Anhand `document_type` (und ggf. Korrespondent-Override) wird das Naming-Template gezogen.
4. Platzhalter werden befüllt; fehlende Pflichtfelder werden im Vorschlag als Platzhalter `{…}` belassen und im UI markiert.
5. `_build_filename_from_meta` arbeitet künftig auf Templates statt auf der festen Reihenfolge `Typ – Aussteller – Betreff – Betrag`.

### Erweitertes LLM-Schema (Anpassung von `ollama_classification.py`)

Vorschlag, zusätzlich zu den bestehenden Feldern:

```json
{
  "document_type": "Wert aus erlaubter Liste oder 'Sonstiges'",
  "document_type_confidence": "0.0 - 1.0",
  "sender_raw": "Roher Aussteller-String",
  "correspondent_hint": "Kurzname, falls eindeutig",
  "subject_short": "max. 6 Wörter, Inhalts-Stichwort",
  "period": { "year": 2024, "month": 11 },
  "reference_number": "Rechnungs-/Police-/Aktenzeichen oder null",
  "extra": {
    "kennzeichen": "...",
    "iban_last4": "...",
    "police_nr": "...",
    "monat_text": "November"
  }
}
```

Die Liste `document_type` wird zur Laufzeit aus `document_types` in den Prompt eingespeist – nicht hardkodiert. Damit sind neue Typen sofort wirksam.

### Few-Shot aus dem Bestand

Beim Import-Vorschlag wird je gemutmaßtem (Dokumenttyp × Korrespondent) ein bis drei Beispiel-Dateinamen aus bereits importierten Dokumenten in den Prompt gehängt. Dadurch lernt die KI das hauseigene Schreibmuster (z. B. „Ausbildungsvergütung Dezember 2014" vs. „Lohnabrechnung 12/2014"). Implementierung: SQL-Query auf `documents` gefiltert nach Typ/Korrespondent, sortiert nach Datum, Top-N.

## Migration

1. `categories` → `document_types` umbenennen (Alembic, mit Spalten `naming_template`, `prompt_hint`, `is_active`, `sort_order`).
2. `Document.category` → `Document.document_type` (Spaltenrename, Backfill 1:1).
3. Index `ix_documents_category` → `ix_documents_document_type`.
4. Frontend-Begriffe austauschen (Vuetify-Strings, Schemas, Saved-Searches-Felder).
5. `correspondents` + `correspondent_aliases` + `correspondent_matchers` neu anlegen.
6. `Document.correspondent_id` (nullable) + Index ergänzen.
7. Seed-Migration mit den oben gelisteten Korrespondenten und Dokumenttypen.
8. Backfill-Job: für vorhandene Dokumente `ai_sender` gegen Matcher laufen lassen und `correspondent_id` setzen, sofern eindeutig (Konfidenz schwellenbasiert, sonst belassen).

## UI/UX-Hinweise

- Settings → Dokumenttypen: vorhandene Kategorien-Seite umbenennen, Template-Editor je Typ.
- Settings → Korrespondenten: CRUD, Aliase, Matcher (inkl. Live-Test gegen den Bestand).
- Import-Stage: Vorschlag zeigt Typ, Korrespondent (mit „neu anlegen"-Option), gefüllte Felder und den daraus erzeugten Dateinamen. Vom Nutzer geänderte Felder werden zurück in den Vorschlag gespeist – kein Rerun des LLM nötig.
- Dokument-Detail: Korrespondent als eigenes Feld neben Dokumenttyp; Anzeige von Aliasen/Matchern, die zugeordnet haben.

## Importer für Altbestand (522 Dokumente)

Mini-CLI bzw. Service-Methode, die für den Bestands-Import:

1. CSV einliest und je Datei eine Vorab-Klassifikation aus Dateiname + erstem OCR-Treffer macht.
2. Den alten Tag-String aufteilt: Mehrfach-Tags (Komma) → mehrere Tags; jede Komponente prüft, ob sie ein Korrespondent ist (Aliase) – ja: setzt `correspondent_id`, nein: bleibt Tag.
3. Tippfehler-Cluster vorschlägt (Levenshtein-Schwellwert) – Beispiel im Bestand: „Privathaftpflicht" vs. „Privathaftpricht".
4. Vorschau pro Datei: alter Name → neuer Name nach Template, Diff sichtbar, Übernehmen einzeln oder bulk.

## Risiken / offene Fragen

- LLM-Halluzinationen bei Korrespondenten: durch Matcher-First-Strategie (deterministisch, danach LLM) minimiert.
- Template-Vielfalt vs. Wartbarkeit: Korrespondent-Overrides nur erlauben, nicht erzwingen.
- Migration `category` → `document_type` betrifft viele Stellen (Routes, Schemas, Frontend). Sauber als eigenständiger Schritt vor allem Korrespondenten-Arbeit ausführen.
- „Krankenkasse" und „Gesundheit" sind im Altbestand vermischt. Beim Import als Pflicht-Klärung lösen.

## Arbeitsschritte (Vorschlag-Reihenfolge)

1. Schema/Begriff: `category` → `document_type` (Tabelle, Spalte, Index, API, UI).
2. `document_types` um `naming_template` und Felder erweitern; Seed mit obiger Liste.
3. LLM-Prompt auf dynamische Typliste umstellen und neue Felder ins JSON-Schema aufnehmen.
4. `correspondents` + Aliase + Matcher + FK auf `documents`; Seed.
5. Filename-Builder auf Templates umstellen; Backwards-kompatibel bei fehlendem Template Fallback aufs bisherige Schema.
6. Few-Shot-Beispiele aus dem Bestand in den Klassifier-Prompt einhängen.
7. Settings-UI für Dokumenttypen-Templates und Korrespondenten.
8. Bestands-Importer mit Vorschau und Bulk-Übernahme.
