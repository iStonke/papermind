# Command-Palette (⌘K) — Umsetzungsplan

> Status: geplant, in Umsetzung · Branch `feat/command-palette` · Stand 2026-07-30

Teil der „Eye-Candy"-Initiative: eine von überall per **⌘K / Ctrl+K**
aufrufbare Command-Palette als erstes Vorzeige-Feature (bestes
Aufwand/Wirkung-Verhältnis). Ein Feld vereint Dokumentsuche, Aktionen,
Navigation und Entitäts-Filter; kontextbewusst je nach aktuellem Ort.

## Umfang v1 (festgelegt)

- **Ergebnistypen:** Dokumente (Titel + OCR-Volltext) · Aktionen · Navigation ·
  Entitäts-Filter (Tags / Korrespondenten / Dokumenttypen).
- **Kein KI-Routing** in v1 (Phase 2, `?`-Modus).
- **Aktionen öffnen den jeweiligen Dialog/View** — nicht mehrstufig inline.
- **Kontextbewusst ab v1**: die Palette kennt das offene Dokument und hebt
  passende Aktionen nach oben.
- **Präfix-Modi:** `>` Aktionen · `#` Tags · `@` Korrespondenten.
- **Zweistufige Suche:** sofort client-seitig über geladene Metadaten;
  OCR-Volltext debounced. In v1 nur „Enter auf der Volltext-Zeile" (filtert die
  Liste, schließt die Palette). **Merge gemischter Backend-Treffer in die
  Palette selbst = Phase 2.**
- Kontextaktionen werden bei aktivem Suchtext als eigene Gruppe **mitgeranked**.

### Kontext-Matrix

| Kontext | Oben (kontextbezogen, bei leerem Feld) | Darunter (immer) |
|---|---|---|
| Reader (Dokument offen) | taggen · Aufbewahrung · annotieren · Wiki generieren · Korrespondent zuweisen · Download · Papierkorb | Aktionen · Springe zu · Filter |
| Dokumentliste (Mehrfachauswahl) | Auswahl taggen · Auswahl-Aufbewahrung · Auswahl löschen | dito |
| Import / Scan | Scannen · Cleanup-Modus · Übernehmen | dito |
| Sonst | — | dito |

## Architektur — Variante A

Eigenes Overlay (kein `v-dialog`), teleportiert in ein Ziel `#pm-overlays`
**innerhalb** von `.papermind-app`.

**Grund:** Die Kontur-Tokens `--pm-*` sind in `frontend/src/theme/theme.css` auf
`.papermind-app` gescoped und vererben sich nur nach unten. Vuetifys `v-dialog`
teleportiert nach `.v-overlay-container` **außerhalb** `.papermind-app` — dort
sind `--pm-*` leer (deshalb baut `SettingsDialog.styles.css` alles aus
`--v-theme-*`-Tripeln). Mit eigenem Teleport-Ziel innerhalb der App steht die
**volle Kontur-Palette + die Motion-Tokens** (`--pm-duration-*`, `--pm-easing`)
direkt zur Verfügung.

**Optik:** streng Kontur — Türkis nur als Zustand (aktive Zeile `--pm-selected`,
Treffer-Highlight, Modus-Badge, Caret), weiße Fläche in Hell / gestufte dunkle
Fläche in Dunkel. `pm-no-animations` und `prefers-reduced-motion` respektieren.

## Andockpunkte im Code

- **Mount:** global + lazy in `frontend/src/views/AppLayout.vue`, exakt wie
  `SettingsDialog`/`AccountDialog` (`defineAsyncComponent`, erst beim ersten
  Öffnen gemountet).
- **Teleport-Ziel:** `<div id="pm-overlays">` innerhalb `<v-app class="papermind-app">`.
- **Zustand:** `frontend/src/stores/ui.js` — `paletteOpen` + `openPalette()` /
  `closePalette()` / `togglePalette()`, gespiegelt vom `settingsOpen`-Muster.
- **⌘K:** `useShortcutScope` (`frontend/src/keyboard/shortcuts.js`) mit eigenem
  Handler `key==='k' && (metaKey||ctrlKey)` — die `SHORTCUTS`-Map kennt keine
  Modifier.
- **Kontextquelle:** `documents.selectedDocumentDetail` (offenes Dokument).
- **Dokumentsuche:** `q`+`search_scope`-Endpunkt in
  `backend/app/routers/documents.py`.
- **Entitäten:** Stores `tags`, `correspondents`, `categories` (= Dokumenttypen).
- **View-Wechsel (Integrations-Hürde):** `activeView` (Dashboard/Tags/Chat) ist
  ein lokaler `ref` in `DocumentsWorkspace.vue`, **kein Store**. Lösung im Stil
  von `ui.signalImportsReload()`: neues Signal `ui.requestView(key)`, das
  `DocumentsWorkspace` per `watch` auf sein `activeView` überträgt.
  Router hat nur `/login` + `/` — Navigation ist also überwiegend
  View-Wechsel/Dialog-Öffner, kaum `router.push`.

## Umsetzungsschritte (stapelbar)

1. **Gerüst:** Teleport-Ziel, `ui`-State, ⌘K-Binding, öffnen/schließen mit
   Scrim-Klick, Escape, Fokus-Falle, Auto-Fokus, Transition über Motion-Tokens.
   A11y: `role="dialog" aria-modal`, Liste als `listbox`, `aria-activedescendant`.
2. **Command-Registry + Dispatch:** deklarative Liste
   `{ id, group, label, icon, keywords, available(ctx), run() }`; `run()` ruft
   bestehende Wege (`ui.openSettings()`, Dialog-Öffner, `ui.requestView(key)`).
3. **Suche + Entitäts-Filter:** Client-Fuzzy (Subsequenz + Präfix-Bonus +
   Recency) über Commands/Dokumente/Entitäten; Präfix-Modi; Volltext-Zeile.
4. **Kontextbewusstsein:** `selectedDocumentDetail` → Kontextaktionen oben,
   mitgeranked bei Suchtext.
5. **Styling & Feinschliff:** `CommandPalette.styles.css` nur mit `--pm-*`;
   Ranking-Tuning, A11y-Durchgang, Tests.

## Phase 2 / später

- KI-Frage-Routing (`?`-Modus) an Chat/AI andocken.
- Merge gemischter Backend-Volltext-Treffer direkt in die Ergebnisliste.
- Mehrstufige Inline-Aktionen (Wert in der Palette wählen, Raycast-Stil).
