# PaperMind (AP9)

Monorepo mit Docker-Compose-Laufzeit:
- Frontend: Vue 3 + Vuetify, statisch gebaut und über Nginx ausgeliefert
- Backend: FastAPI + SQLAlchemy + Alembic
- DB: PostgreSQL 17 + pgvector
- AI-Service: Embedding-API (lokales Modell)
- Worker: OCR-Pipeline mit OCRmyPDF

Aktueller Scope:
- OCR-Job-Orchestrierung über API (`/api/documents/{id}/ocr`)
- Asynchrone OCR-Ausführung im Worker-Container (kein OCR im Web-Request)
- OCR-Datei (`ocr.pdf`) + Textpersistenz (`documents.text_content`)
- OCR-Qualitätsstatus (`good|warning|error`) inkl. Konfidenzscore für KI-Verlässlichkeit
- UI: OCR-Status, OCR-Start/Retry, Viewer-Umschaltung Original/OCR
- Volltextsuche mit PostgreSQL FTS (`original_filename`, `notes`, `text_content`)
- Zentrale AppBar-Suche mit Snippets/Highlight in der Dokumentliste
- AP6 Tag-Management mit Tag-View, Tag-Wolke, Merge/Rename/Delete
- AP7 Intelligente Ordner (Saved Searches / Smart Folders)
- AP8 Retrieval-Basis:
  - Chunking + Embeddings in PostgreSQL/pgvector
  - INDEX-Job-Pipeline (automatisch nach OCR/bei textful Upload)
  - Retrieval-Endpoint für Top-k Chunks inkl. Score/Metadaten
- AP9 KI-Bereich:
  - KI-Seite mit Vorschlagsfragen + Chat
  - `/api/ai/ask` liefert Antwort + Quellenkarten
  - Quellenkarten öffnen Dokument + Seite in der Bibliothek
- APx Dublettenprüfung (v1):
  - exakte Duplikate via `file_sha256` (Upload-Block mit `409`)
  - inhaltliche Duplikate via `text_simhash64` (Markierung als probable duplicate)

## Docker Desktop / Compose

- Compose-Projektname ist fixiert:
  - `.env`: `COMPOSE_PROJECT_NAME=papermind`
  - `docker-compose.yml`: `name: papermind`

Prüfen:
```bash
docker context ls
docker compose ls
```

## Standard-Ports

- Frontend: `5179`
- Backend: `8040`
- DB: `5440`
- AI: `11439`

Bei Konflikten Ports in `.env` anpassen.

## Start / Stop

Alltag (Compose-Gruppe in Docker Desktop behalten):
```bash
docker compose up -d --build
docker compose up -d --build worker
docker compose stop
docker compose start
```

Aufräumen:
```bash
docker compose down
```

## Tests / CI

Lokale Basisprüfung:
```bash
./scripts/test.sh
```

Backend-Dev-Abhängigkeiten installieren:
```bash
python3 -m pip install -r backend/requirements-dev.txt
```

Einzelne Prüfungen:
```bash
PYTHONPATH=backend python3 -m pytest backend/tests
npm --prefix frontend test
npm --prefix frontend run build
```

Die GitHub-Actions-CI führt Backend-Tests, Alembic-Migrationen gegen
PostgreSQL/pgvector, Frontend-Tests und den Frontend-Produktionsbuild aus.

## Raspberry Deployment Update

Im geklonten Repo auf dem Pi:
```bash
cd /opt/papermind
chmod +x scripts/deploy_pi.sh
```

Nur Code-Update (fast-forward pull auf `main`):
```bash
./scripts/deploy_pi.sh
```

Mit Container-Update:
```bash
./scripts/deploy_pi.sh --compose --build
```

Worker gezielt neu bauen/starten:
```bash
./scripts/deploy_pi.sh --compose --build --worker
```

## Produktionsbetrieb

`docker-compose.yml` verwendet bereits den statischen Frontend-Build. Für den
gehärteten Betrieb auf dem Raspberry/Heimnetz gibt es zusätzlich
`docker-compose.prod.yml` ohne Quellcode-Volumes und mit TLS-Reverse-Proxy:

- Frontend wird statisch gebaut und über Nginx ausgeliefert.
- `/api/*` läuft same-origin über den Nginx-Proxy zum Backend.
- Öffentlich gebunden wird nur `FRONTEND_PORT`.
- Backend, PostgreSQL und AI-Service sind nur im Compose-Netz erreichbar.
- Es werden keine Quellcode-Dev-Volumes in Backend, Frontend oder AI gemountet.
- Der OCR/Index-Worker startet standardmäßig mit und wartet auf das migrierte,
  einsatzbereite Backend.

Einmalig konfigurieren:
```bash
cp .env.prod.example .env.prod
```

Dann Platzhalter in `.env.prod` ersetzen, insbesondere:
- `POSTGRES_*`
- `DATABASE_URL`
- `PUBLIC_WEB_BASE_URL`
- `CORS_ALLOW_ORIGINS`
- `AUTH_SECRET_KEY`

Produktionsstack starten:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Worker bei Bedarf gezielt neu bauen:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build worker
```

Update über Deploy-Skript:
```bash
./scripts/deploy_pi.sh --prod --compose --build --worker
```

Status prüfen:
```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

Backup der Datenbank:
```bash
mkdir -p backups
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "backups/papermind-db-$(date +%Y%m%d-%H%M%S).sql"
```

Backup der PDF-Dateien:
```bash
mkdir -p backups
docker run --rm \
  -v papermind_pdf_storage:/data:ro \
  -v "$PWD/backups:/backup" \
  alpine tar czf "/backup/papermind-files-$(date +%Y%m%d-%H%M%S).tar.gz" -C /data .
```

## Worker-Profil (OCR)

- Worker läuft im Compose-Profil `worker`.
- Der Worker mountet `pdf_storage` unter `STORAGE_PATH`.
- Pollt `queued` OCR-Jobs und setzt Status: `queued -> running -> done/failed`.

Wichtige ENV-Variablen:
- `AUTO_OCR_ON_UPLOAD=true` (wenn `true`: OCR wird nur bei textarmen PDFs automatisch gestartet)
- `MIN_TEXT_CHARS=300` (Schwellwert für "textful" PDFs, gemessen als Nicht-Whitespace-Zeichen)
- `TEXT_CHECK_PAGES=2` (Anzahl Seiten für schnellen Text-Check beim Upload)
- `WORKER_POLL_INTERVAL_SECONDS=3`
- `WORKER_OCR_TIMEOUT_SECONDS=900`
- `SEARCH_QUERY_MAX_LENGTH=256`
- `FTS_LANGUAGE=german` (`german` oder `simple`)
- `INDEX_AUTO_ON_READY=true`
- `EMBED_MODEL=hash-384-v1`
- `EMBED_DIM=384`
- `EMBED_BATCH_SIZE=32`
- `CHUNK_SIZE_CHARS=1000`
- `CHUNK_OVERLAP_CHARS=100`
- `EMBED_MAX_TEXTS=64` (AI `/embed` max batch)
- `EMBED_MAX_CHARS=4000` (AI `/embed` max text length)
- `AI_EMBED_TIMEOUT_SECONDS=30`
- `RETRIEVAL_MAX_TOP_K=20`
- `DEDUPE_CANDIDATE_LIMIT=200`
- `DEDUPE_TEXT_DISTANCE_THRESHOLD=6`

## AP5 Datenmodell

Migrationen:
- `001_initial`
- `002_document_files`
- `003_ocr_pipeline_fields`
- `004_documents_fts`
- `005_fts_filename_tokens`
- `006_fts_dual_lang_vector`
- `007_text_source_embedded`
- `008_saved_searches`
- `009_documents_unread_flag`
- `010_ap8_embeddings`
- `011_documents_display_name`
- `012_documents_dedupe_fields`

Neue/erweiterte Felder:
- `documents.text_content` (`TEXT`, nullable)
- `documents.text_source` (`none|embedded|ocr`)
- `documents.ocr_status` (`not_started|queued|running|done|failed`)
- `documents.ocr_quality_status`, `documents.ocr_confidence_score`, `documents.ocr_quality_message`, `documents.ocr_processing_seconds`
- `documents.embedding_status` (`not_started|queued|running|done|failed`)
- `documents.embedding_model`, `documents.embedding_dim`, `documents.embedding_error`
- `documents.text_hash`, `documents.embedding_updated_at`
- `documents.file_sha256`, `documents.file_size_bytes`
- `documents.text_hash_sha256`, `documents.text_simhash64`
- `documents.simhash_bucket1..4`
- `documents.first_page_phash64` (v1.1 vorbereitet)
- `documents.duplicate_of_doc_id`, `documents.duplicate_kind`, `documents.duplicate_score`, `documents.duplicate_checked_at`
- `jobs.started_at`, `jobs.finished_at`

AP8 Tabellen:
- `doc_chunks`
  - `doc_id`, `chunk_index`, `page_from`, `page_to`, `text`, `char_len`, `content_hash`, ...
- `doc_embeddings`
  - `chunk_id`, `model`, `dim`, `embedding vector(384)`
  - HNSW Index auf `embedding` (`vector_cosine_ops`)

OCR-Konfliktschutz:
- Partial Unique Index: pro Dokument maximal ein aktiver OCR-Job (`queued|running`).

Dubletten-Konfliktschutz:
- Partial Unique Index: `uq_documents_file_sha256_not_null` auf `documents.file_sha256`.
- Exakter Duplikat-Upload liefert `409` mit `error.code = DUPLICATE_EXACT` und `existing_doc_id`.
- Inhaltliche Duplikate werden markiert (`duplicate_kind='text'`), aber nicht blockiert.

AP5.1 Upload-Verhalten (OCR nur bei Bedarf):
- Nach dem Speichern von `original.pdf` führt das Backend einen schnellen Text-Check auf den ersten `TEXT_CHECK_PAGES` Seiten aus.
- Wenn die erkannte Textmenge `>= MIN_TEXT_CHARS` ist:
  - kein OCR-Job
  - `documents.status=ready`
  - `documents.text_source=embedded`
  - `documents.text_content` wird direkt aus eingebettetem PDF-Text befüllt.
- Wenn die Textmenge darunter liegt:
  - bei `AUTO_OCR_ON_UPLOAD=true` wird OCR gequeued (`status=processing`)
  - bei `AUTO_OCR_ON_UPLOAD=false` bleibt das Dokument ohne Auto-OCR im Import-Status.
- Falls der Text-Check fehlschlägt, greift Fail-Safe: bei aktiviertem Auto-OCR wird trotzdem ein OCR-Job angelegt (mit Warn-Log).

FTS:
- `documents.search_vector` (`tsvector`)
- Trigger `trg_documents_search_vector` aktualisiert den Vektor bei Insert/Update von `original_filename`, `notes`, `text_content`
- GIN-Index: `ix_documents_search_vector`
- Sprachkonfiguration via ENV:
  - `FTS_LANGUAGE=german` (Default)
  - `FTS_LANGUAGE=simple` (Fallback bei Stemming-Problemen)

## Storage-Struktur

Volume: `pdf_storage` (Backend + Worker über `STORAGE_PATH`).

```text
/pdf_storage/{document_id}/
  original.pdf
  thumbnail.png
  ocr.pdf
```

`file_key` ist immer relativ (z. B. `{document_id}/ocr.pdf`).

## API (AP5)

### OCR triggern

`POST /api/documents/{id}/ocr`

Verhalten:
- prüft Dokument + `original` Datei
- legt OCR-Job an (`type=OCR`, `status=queued`)
- setzt Dokument auf `status=processing`, `ocr_status=queued`
- löscht alte OCR-Qualitätswerte, bis der Worker neue Werte berechnet
- Antwort: `202` + aktuelles `DocumentDetail`
- falls OCR bereits aktiv: `409 CONFLICT`

### Index/Embedding triggern

`POST /api/documents/{id}/index?force=false`

Verhalten:
- queued INDEX-Job für Chunking + Embeddings
- setzt `embedding_status=queued`
- `force=true` setzt `text_hash` zurück, um Reindex zu erzwingen
- falls INDEX bereits aktiv: `409`

### Retrieval (AP8)

`POST /api/retrieval/query`

Body:
```json
{
  "query": "rechnung auto service",
  "top_k": 5,
  "filters": {
    "doc_id": null,
    "tag_ids": [],
    "date_from": null,
    "date_to": null
  }
}
```

Response enthält:
- `results[]`: `doc_id`, `chunk_id`, `chunk_index`, `page_from`, `page_to`, `score`, `text`
- `timings`: `embed_ms`, `db_ms`, `total_ms`

### KI Ask (AP9)

`POST /api/ai/ask`

Body:
```json
{
  "question": "Welche Zahlungsfrist steht in den Rechnungen?",
  "top_k": 5,
  "doc_id": null
}
```

Response enthält:
- `answer`: Antworttext
- `citations[]`: `doc_id`, `chunk_id`, `chunk_index`, `page`, `score`, `snippet`, `document_title`
- `debug`: Retrieval- und LLM-Timings

Hinweis:
- Der Backend-Flow ist `Retrieval -> AI /chat -> Antwort + Quellen`.
- Falls `/chat` nicht verfügbar ist, nutzt das Backend eine sichere Fallback-Antwort auf Basis der Top-Chunks.

### Debug-Endpunkte (AP8)

`GET /api/documents/{id}/chunks`
- zeigt Chunk-Liste (`chunk_index`, `page_from/to`, `char_len`, `content_hash`)

`GET /api/documents/{id}/embedding-status`
- zeigt `embedding_status`, `chunk_count`, `embedded_count`, `model`, `dim`, `last_error`

### Datei-Ausgabe

`GET /api/documents/{id}/file?role=original|ocr`

- default `role=original`
- inline delivery (kein forced download) für Preview
- mit `download=true` wird bewusst als Attachment ausgeliefert
- bei fehlender `ocr`-Datei: `404`

### Dokumentsuche

`GET /api/documents?q=...`

- durchsucht per FTS: Dateiname + Notizen + OCR-Text
- liefert bei `q` zusätzlich `snippet` und `rank` je Treffer
- kombiniert mit bestehenden Filtern (`status`, `date_from`, `date_to`, `tag`, Pagination)
- Tag-Filter bevorzugt über `tag_id=<uuid>` (legacy `tag` bleibt kompatibel)

### Tag-Management (AP6)

`GET /api/tags?include_count=true`
- liefert pro Tag zusätzlich `usage_count`
- default Sortierung: `usage_count DESC`, dann Name

`POST /api/tags/{source_id}/merge`
- Body: `{ "target_id": "<uuid>" }`
- überträgt alle Beziehungen von `source_id` nach `target_id`
- dedupliziert Beziehungen (`document_id`,`tag_id`)
- löscht danach den Quell-Tag
- validiert:
  - `400` bei `source_id == target_id`
  - `404` wenn source/target fehlt

`PATCH /api/tags/{id}`
- robustes Rename (trim + Whitespace-Normalisierung)
- case-insensitive Konflikte liefern `409`

### Intelligente Ordner (AP7)

`GET /api/saved-searches`
- Liste der Smart Folders (`id`, `name`, Zeitstempel)

`GET /api/saved-searches/{id}`
- Detail inkl. `query_json`

`POST /api/saved-searches`
- Body: `{ "name": "...", "query": { ... } }`
- speichert `q`, `tagId`, `status`, `dateFrom`, `dateTo`, `sort`, `order`
- `limit/offset` werden nicht persistiert

`PATCH /api/saved-searches/{id}`
- unterstützt `name` und/oder `query`

`DELETE /api/saved-searches/{id}`
- löscht Smart Folder

## UI (AP5)

- AppBar enthält `Importieren`-Dialog (Modal, Multi-Upload-Queue).
- iOS-Scans können über die SMB-Freigabe `PaperMind Scans` in `./scan-inbox` gespeichert werden; der Worker übernimmt stabile PDFs in die Import-Inbox und die App zeigt eine Badge am `Importieren`-Button. Details: `docs/smb-scan-inbox.md`.
- Rechtes Panel zeigt OCR-Statuskarte mit Progress + Fehlertext.
- Bei OCR-Qualität `warning` oder `error` zeigt die App eine Warnung; `error` bedeutet manuelle Prüfung empfohlen.
- Button `OCR starten` / `OCR erneut starten`.
- Viewer-Toggle: `Original` / `OCR`.
- Expliziter Button `Herunterladen` (nur dieser löst Download aus).
- Wenn OCR-Datei verfügbar ist, wird beim Öffnen eines Dokuments standardmäßig OCR angezeigt.
- Polling aktualisiert laufende OCR-Status automatisch.
- AppBar-Suche ist an `/api/documents` angebunden (Debounce + Enter sofort).
- Suchmodus zeigt eine dezente Zeile über der Liste: `Suche: ...` + `Zurücksetzen`.
- Treffer zeigen im List-Item ein Snippet mit Highlight (`<mark>`).
- Linke Leiste enthält Tag-Bereich:
  - `Alle Tags` öffnet Tag-View in der mittleren Spalte
  - Top-5 Quicklinks nach `usage_count`
- Tag-View (mittlere Spalte):
  - ruhige Tag-Wolke (Gewichtung über `usage_count`)
  - Tag-Liste mit Aktionen: Erstellen, Umbenennen, Zusammenführen, Löschen
  - Klick auf Tag filtert die Dokumentliste direkt
- Aktiver Tag-Filter wird oberhalb der Dokumentliste als entfernbarer Chip angezeigt.
- Sidebar enthält den Bereich `Ordner`:
  - `Ordner erstellen` speichert den aktuellen Listen-Filterzustand als Smart Folder
  - Klick auf einen Ordner stellt den gespeicherten Filterzustand wieder her
  - Actions je Ordner: Umbenennen, Aktualisieren (Query überschreiben), Löschen
- Wenn ein Smart Folder aktiv ist, erscheint oberhalb der Liste ein Chip `Ordner: <Name>`.

Suchsyntax (AP5 minimal):
- `status:ready|processing|failed|imported`
- `date:YYYY-MM-DD..YYYY-MM-DD`
- Restlicher Text wird als Freitext für FTS gesucht.
- Ungültige Token werden ruhig gemeldet und als Freitext behandelt (Best-Effort).
- Parsing erfolgt im Frontend (AppBar) und wird auf API-Parameter (`q`, `status`, `date_from`, `date_to`) abgebildet.

## Validierung (schnell)

1) Projekt starten:
```bash
docker compose up -d --build
docker compose up -d --build worker
```

2) Upload:
```bash
curl -sS -X POST "http://localhost:8040/api/documents/upload" \
  -F "file=@/absolute/path/to/scanned.pdf;type=application/pdf"
```

3) OCR starten:
```bash
curl -sS -X POST "http://localhost:8040/api/documents/<DOC_ID>/ocr"
```

4) Volltextsuche prüfen:
```bash
curl -sS "http://localhost:8040/api/documents?q=rechnung"
```

5) Status prüfen:
```bash
curl -sS "http://localhost:8040/api/documents/<DOC_ID>"
```

6) OCR-Datei prüfen:
```bash
curl -I "http://localhost:8040/api/documents/<DOC_ID>/file?role=ocr"
docker run --rm -v papermind_pdf_storage:/data alpine sh -lc "find /data -maxdepth 3 -type f | sort"
```

7) Worker-Logs:
```bash
docker compose logs -f worker
```

8) AP5 Smoke-Test (FTS + Syntax):
```bash
BASE_URL=http://localhost:8040 ./backend/scripts/smoke_ap5.sh
# falls localhost in deiner Umgebung nicht direkt erreichbar ist:
API_VIA_COMPOSE=true BASE_URL=http://127.0.0.1:8040 ./backend/scripts/smoke_ap5.sh
```

9) AP8 Embedding + Retrieval:
```bash
# INDEX manuell starten
curl -sS -X POST "http://localhost:8040/api/documents/<DOC_ID>/index?force=true"

# Status prüfen
curl -sS "http://localhost:8040/api/documents/<DOC_ID>/embedding-status"
curl -sS "http://localhost:8040/api/documents/<DOC_ID>/chunks"

# Retrieval testen
curl -sS -X POST "http://localhost:8040/api/retrieval/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"rechnung auto service","top_k":3,"filters":{"doc_id":"<DOC_ID>","tag_ids":[],"date_from":null,"date_to":null}}'
```

## Troubleshooting

- `POST /ocr` gibt `409`: Es läuft bereits ein OCR-Job (`queued` oder `running`).
- `role=ocr` gibt `404`: OCR ist noch nicht fertig oder fehlgeschlagen.
- Worker startet nicht: Backend-Readiness, Migrationen und Worker-Logs prüfen.
- OCR-Fehler im Job: `jobs.error_message` prüfen + `worker` Logs ansehen.
- Suche findet nichts trotz OCR: prüfen, ob OCR abgeschlossen ist (`ocr_status=done`) und `q` nicht nur Whitespace ist.

## OpenAPI

- Swagger UI: `http://localhost:8040/docs`
