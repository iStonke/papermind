# PaperMind – Lernbereich: Datenmodell

*Technische Ausformulierung zu §10 (Punkt 1) des Konzepts (`lernbereich-konzept.md`).
Grundlage: Code-Prüfung des bestehenden Notiz-Stacks am 10.–21.09.2026.
Alle Entscheidungen sind an vorhandene PaperMind-Muster angelehnt, damit der
Lernbereich erbt statt neu erfindet.*

---

## 0. Was der Code schon liefert (und was der Lernbereich davon erbt)

| Vorhandenes Element | Ort | Wird im Lernbereich zu … |
|---|---|---|
| Notiz als ProseMirror-**JSONB** (`note.body_json`) + denormalisiertes `body_text` + `search_vector` | `backend/app/models/note.py:43` | Substanz-Ebene der Mitschrift. **Kein** neues Notizformat. |
| `NoteLink` (denormalisierter Verweis `target_type` document\|correspondent\|dossier\|note) | `note.py:135` | Vorbild + evtl. Ziel für Artefakt→Notiz-Verweise. |
| `NoteTask` als **Projektion** aus `body_json`, neu berechnet in `_sync_tasks()` bei jedem Save | `note_service.py:403` | Blaupause für die Marker-Projektion (§3.4). |
| `Annotation` (PDF-Highlight): `document_id`, `page`, `rects` JSONB, `quote`, `prefix`, `suffix`, RLS-owner-scoped | `backend/app/models/annotation.py` | **Anker-Typ 2 komplett** – wird nur referenziert. |
| UUID-PKs, `owner_id` + RLS (Migration 041), JSONB überall, Alembic bis **093** | durchgängig | Konventionen für alle neuen Tabellen. |

**Nächste freie Migrationsnummer: `094`.**

---

## 1. Fundament: stabile Node-IDs (keine Migration)

Das einzige echte Loch aus §10. Heute ankert PaperMind Knoten **positionell**
(`set_taskitem_checked(body_json, position)`, `note_service.py:193`) — das bricht,
sobald oberhalb etwas eingefügt wird. Für Lernartefakte, die Wochen später auf
*genau eine* markierte Zeile zurückspringen (§4, §9.3), reicht das nicht.

**Lösung – rein im Frontend, ohne DB und ohne Massen-Migration alter Notizen:**

- Eine TipTap-Extension `StableId` ergänzt per `addGlobalAttributes()` das Attribut
  **`pmId`** (Kurz-UUID) auf den markierbaren Block-Node-Typen (`paragraph`, `heading`,
  `taskItem`, `checkListItem`, `blockquote`, Layout-Blöcke).
- **Lazy-Vergabe:** `pmId` wird *nicht* beim Laden über alle Knoten gestreut, sondern
  erst gesetzt, **wenn ein Knoten markiert wird** (oder ein Artefakt daran hängt).
  Altnotizen bleiben unangetastet; nur lernrelevante Knoten bekommen eine ID.
- **Kollisionsregel bei Split/Paste:** Wird ein Block mit vorhandener `pmId` geteilt
  oder kopiert, behält *einer* die ID, alle Kopien bekommen neue (appendTransaction,
  etabliertes `UniqueID`-Muster).

Der **Marker** selbst ist ein zweites Block-Attribut `learn` auf denselben Knoten:

```jsonc
{ "type": "paragraph",
  "attrs": { "pmId": "a1b2c3d4",
             "learn": { "kind": "fakt", "slide": "S9" } },
  "content": [ { "type": "text", "text": "homogene Koordinaten: (x,y) → (x,y,1)" } ] }
```

- Live wird nur `kind: "lernen"` (generisch) + optional `slide` gesetzt — **eine** Taste
  (§6.1, §5.3). Der genaue Typ entsteht erst in der Nachbereitung.
- Der **Folienanker** `@S12` lebt als `attrs.learn.slide`, nicht als eigener Knoten.

> **Damit ist der Anker der Notiz = `(note_id, pmId)` — stabil über Edits.**

---

## 2. Objektmodell (Überblick)

```
learn_course ──< learn_session ──(note_id)──> note        (Substanz)
     │  │              │
     │  │              └─ Slides/Skript-Anker zeigen in ──> documents (Substanz)
     │  └──< learn_course_source ──> documents            (Retrieval-Korpus, §7.4)
     │
     ├──< learn_artifact ──< learn_anchor ──┬─ note_node:      (note_id, pmId)
     │        │                             ├─ pdf_highlight:  annotation_id
     │        │                             ├─ slide:          (document_id, slide_label)
     │        │                             └─ placeholder:    ts + hint (später gebunden)
     │        └─ provenance / verify_status / state
     │
     └──< learn_sheet ──< learn_sheet_artifact ──> learn_artifact   (n:m, geordnet/gruppiert)

Raw-Marker-Pool (Nachbereitungsliste):
  learn_marker            (Projektion aus note.body_json — wie note_task)
  learn_highlight_marker  (Opt-in-Tag auf bestehender annotation)
```

Alle Tabellen: `id UUID PK default uuid4`, `owner_id UUID NOT NULL` (RLS-Isolation
analog Migration 041), `created_at`/`updated_at` mit `server_default=func.now()`.

---

## 3. Tabellen

### 3.1 `learn_course` — Kurs (§3)

| Spalte | Typ | Null | Bemerkung |
|---|---|---|---|
| `title` | Text | – | z. B. „Computergrafik 1" |
| `module_key` | String(64) | ✓ | Kürzel für Modul-Profile (§10) |
| `default_artifact_type` | String(24) | – | Vorbelegung (§5.3); default `fakt` |
| `has_script` | Boolean | – | §7.4-Flag: brauchbares Skript → Fall-A-Antworten anbieten |
| `color` | String(16) | ✓ | optional, analog `note_collection` |
| `is_archived` | Boolean | – | default false |

### 3.2 `learn_course_source` — Foliensätze/Skripte des Kurses (§3, §7.4)

Retrieval-Korpus + Auswahlmenge für Slide-Anker. Join Kurs ↔ PDF.

| Spalte | Typ | Null | Bemerkung |
|---|---|---|---|
| `course_id` | UUID FK→`learn_course` CASCADE | – | |
| `document_id` | UUID FK→`documents` CASCADE | – | vorhandenes PDF |
| `role` | String(16) | – | `script` \| `slides` |
| `label` | String(120) | ✓ | Anzeigename |
| `position` | Integer | – | default 0 |

*Kein separates `learn_session_source`:* Welche Folien eine Sitzung betrifft, ergibt sich
aus ihren Slide-Ankern.

### 3.3 `learn_session` — Sitzung (§3)

| Spalte | Typ | Null | Bemerkung |
|---|---|---|---|
| `course_id` | UUID FK→`learn_course` CASCADE | – | |
| `title` | Text | – | |
| `session_date` | Date | ✓ | |
| `note_id` | UUID FK→`note` **SET NULL** | ✓ | **genau eine** Mitschrift |
| `ordinal` | Integer | – | default 0 |

### 3.4 `learn_marker` — Notiz-Marker-Pool (Projektion, §3/§4)

`note_task`-Muster: bei jedem Notiz-Save aus `body_json` **neu berechnet**
(`_sync_learn_markers()`). Ephemer — die Wahrheit ist die Notiz.

| Spalte | Typ | Null | Bemerkung |
|---|---|---|---|
| `note_id` | UUID FK→`note` CASCADE, index | – | |
| `node_pm_id` | String(16) | – | die stabile `pmId` (§1) |
| `marker_kind` | String(16) | – | `lernen`\|`fakt`\|`warum`\|`aufgabe`\|`analyse`\|… |
| `slide_label` | String(16) | ✓ | aus `attrs.learn.slide` |
| `snippet` | Text | – | denormalisierter sichtbarer Text (gekürzt) |
| `position` | Integer | – | Dokumentreihenfolge (Anzeige/Sortierung) |

- **Eindeutigkeit:** `UNIQUE(note_id, node_pm_id)`.
- **„Verarbeitet?"** wird berechnet: Marker ist verarbeitet, wenn ein
  `learn_anchor(kind=note_node, note_id, node_pm_id)` existiert. Nachbereitungs-Query =
  `learn_marker LEFT JOIN learn_anchor … WHERE anchor IS NULL`.

### 3.5 `learn_highlight_marker` — PDF-Marker-Pool (Opt-in-Tag, §4 Typ 2)

Ein schmaler Tag markiert ein vorhandenes `annotation`-Highlight als lernrelevant —
**ohne die `annotations`-Tabelle anzufassen**.

| Spalte | Typ | Null | Bemerkung |
|---|---|---|---|
| `annotation_id` | UUID FK→`annotations` CASCADE, **UNIQUE** | – | das getaggte Highlight |
| `marker_kind` | String(16) | – | wie oben |

*Leichtere Alternative:* nullable Spalte `annotations.learn_kind`. Seitentabelle hält den
Lernbereich additiv — empfohlen für v1.

### 3.6 `learn_artifact` — Artefakt (§5, §7, §8)

| Spalte | Typ | Null | Bemerkung |
|---|---|---|---|
| `course_id` | UUID FK→`learn_course` CASCADE, index | – | |
| `session_id` | UUID FK→`learn_session` SET NULL | ✓ | Herkunfts-Sitzung |
| `type` | String(24) | – | `fakt`\|`prozess`\|`zusammenhang`\|`prozedural`\|`verstaendnis`\|`uebung` |
| `front` | JSONB | – | Frage/Aufgabe (KI-Transformation, editierbar) |
| `solution` | JSONB | ✓ | **nur** legitimer Eigen-Content (§2.1): Rechenweg Typ 6, Tabelle Typ 3. Bei Typ 1/5 leer. |
| `provenance` | String(24) | – | `note`\|`script`\|`external_unverified`\|`manual` (§8.1) |
| `source_ref` | String(120) | ✓ | z. B. `skript S.9` |
| `source_document_id` | UUID FK→`documents` SET NULL | ✓ | Skript-Zitat (§7.4 Fall A) |
| `source_page` | Integer | ✓ | Seitenbeleg |
| `verify_status` | String(12) | – | `na`\|`unverified`\|`verified` (§8.2) |
| `ai_generated` | Boolean | – | KI-Vorschlag war Ursprung |
| `ai_accepted` | Boolean | ✓ | angenommen/verworfen (§6.3) |
| `state` | JSONB | – | Lernzustand (§9.3), default `{}`; SRS-Algorithmus offen |
| `is_deleted` | Boolean | – | Soft-Delete |

**Regeln (setzen §2.1 durch):** Typ 1/5 → `solution` leer (Antwort = Anker). Typ 5 →
`front` ohne KI-Antwort. `provenance='external_unverified'` erzwingt sichtbares Flag +
`verify_status` bleibt sichtbar bis `verified`.

### 3.7 `learn_anchor` — Anker (§4)

Ein Artefakt kann **mehrere** Anker haben. Polymorph über `kind`.

| Spalte | Typ | Null | Bemerkung |
|---|---|---|---|
| `artifact_id` | UUID FK→`learn_artifact` CASCADE, index | – | |
| `kind` | String(16) | – | `note_node`\|`pdf_highlight`\|`slide`\|`placeholder` |
| `role` | String(12) | – | `source` \| `context`; default `source` |
| `note_id` | UUID FK→`note` SET NULL | ✓ | kind=note_node |
| `node_pm_id` | String(16) | ✓ | kind=note_node — stabile ID (§1) |
| `annotation_id` | UUID FK→`annotations` SET NULL | ✓ | kind=pdf_highlight |
| `document_id` | UUID FK→`documents` SET NULL | ✓ | kind=slide |
| `slide_label` | String(16) | ✓ | kind=slide, z. B. `S12` |
| `page` | Integer | ✓ | kind=slide (aufgelöste Seite) |
| `placeholder_ts` | DateTime | ✓ | kind=placeholder |
| `placeholder_hint` | Text | ✓ | kurze Tippbeschreibung |
| `resolved` | Boolean | – | placeholder gebunden? default false |

- **Dangling statt Löschen:** Verschwindet ein `pmId` aus der Notiz oder wird die Annotation
  gelöscht (SET NULL), wird der Anker *verwaist*; das Artefakt bleibt und wird als „Quelle
  fehlt" markiert (PaperMind-Muster „Verwaist").

### 3.8 `learn_sheet` — Lernblatt (§3, §2.1)

| Spalte | Typ | Null | Bemerkung |
|---|---|---|---|
| `course_id` | UUID FK→`learn_course` CASCADE | – | |
| `session_id` | UUID FK→`learn_session` SET NULL | ✓ | `null` = themenübergreifend |
| `title` | Text | – | |
| `scope` | String(12) | – | `session`\|`topic` |
| `structure` | JSONB | – | legitimer Eigen-Content: Gruppen + Reihenfolge + Überblickssätze |

```jsonc
{ "groups": [
    { "id": "g1", "title": "Homogene Koordinaten",
      "overview": "Der Trick, der Translation zur Matrixmult. macht.",
      "artifact_ids": ["…","…"] } ] }
```

### 3.9 `learn_sheet_artifact` — Blatt↔Artefakt (n:m)

Denormalisierte Mitgliedschaft für Rückwärts-Query (wie `note_link`). Gruppen-Metadaten in
`structure`, Zuordnung hier.

| Spalte | Typ | Null | Bemerkung |
|---|---|---|---|
| `sheet_id` | UUID FK→`learn_sheet` CASCADE, index | – | |
| `artifact_id` | UUID FK→`learn_artifact` CASCADE, index | – | |
| `group_id` | String(16) | ✓ | Schlüssel in `structure.groups[].id` |
| `position` | Integer | – | default 0 |

`UNIQUE(sheet_id, artifact_id)`.

---

## 4. Sync- & Lebenszyklus-Regeln

1. **Marker-Projektion** (`_sync_learn_markers`): im `NoteService` neben `_sync_tasks`
   einhängen — walk über `body_json`, sammelt Knoten mit `attrs.learn != null`, schreibt
   `learn_marker` neu. **Keyed über `attrs.pmId`**, nicht über die Position.
2. **Artefakt-Erzeugung** (Nachbereitung, §6.3): aus `learn_marker` → neues `learn_artifact`
   (Typ = Kurs-Default) + `learn_anchor(kind=note_node, …)`. Der Marker verschwindet nicht;
   „verarbeitet" = Existenz des Ankers.
3. **Verwaisung** statt Löschung (§3.7); periodischer/lazy Check markiert verwaiste Artefakte.
4. **Owner/RLS:** jede Tabelle `owner_id` + RLS analog `annotations_owner_isolation`. Reines
   Nutzerobjekt (kein Worker-Pfad).

---

## 5. Migrationsplan

| Nr | Inhalt |
|---|---|
| **094** | `learn_course`, `learn_course_source`, `learn_session`, `learn_artifact`, `learn_anchor`, `learn_sheet`, `learn_sheet_artifact` (Kern) + RLS + Indizes |
| **095** | `learn_marker`, `learn_highlight_marker` (Marker-Pool) — hängt am `NoteService`-Sync |
| *(kein DB-Schritt)* | stabile `pmId` = TipTap-Extension `StableId` + `_sync_learn_markers` |

Reihenfolge: zuerst `pmId` (Fundament), dann 094/095, dann KI/Retrieval (§7.4).

---

## 6. Zwei Entscheidungen, die noch offen sind

1. **PDF-Marker: Seitentabelle `learn_highlight_marker` (additiv)** vs. Spalte
   `annotations.learn_kind` (schlanker, koppelt). Empfehlung: Seitentabelle für v1.
2. **`learn_sheet_artifact` (normalisierte n:m)** vs. alles in `structure` JSONB.
   Empfehlung: normalisiert — folgt der `note_link`-Entscheidung im Bestand.

---

## 7. UX-Verankerung (siehe Konzept §11)

- Die **Nachbereitung** ist ein eigener Review-Bildschirm pro Sitzung; ihre Warteschlange
  ist die Query aus §3.4 („Marker ohne Anker").
- Der **sanfte Anstupser** (Variante B) ist eine zusätzliche Kachel-Art in
  `/api/dashboard/overview`, gespeist aus derselben Query, nach Sitzung gruppiert.
