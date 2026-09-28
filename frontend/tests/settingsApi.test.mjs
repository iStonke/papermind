import test from "node:test";
import assert from "node:assert/strict";

import {
  buildAutoOpenImportInboxPatch,
  buildAutoOcrPatch,
  buildAutoTaggingPatch,
  buildRecentImportWindowPatch,
  buildNotesPreferencesPatch,
  buildDashboardQuickActionsPatch,
  buildSidebarMaxFoldersPatch,
  buildSidebarShowDossiersPatch,
  buildSidebarShowLernraumPatch,
  buildSortOrderPatch,
  buildThemeModePatch,
  buildTrashRetentionPatch,
  normalizeNoteTextReplacements,
} from "../src/utils/settingsApi.js";

test("buildDashboardQuickActionsPatch only includes supplied actions", () => {
  assert.deepEqual(buildDashboardQuickActionsPatch({ showImport: false }), {
    ui: { dashboard_show_import_action: false },
  });
  assert.deepEqual(buildDashboardQuickActionsPatch({ showImport: true, showNote: false }), {
    ui: {
      dashboard_show_import_action: true,
      dashboard_show_note_action: false,
    },
  });
});

test("buildThemeModePatch returns expected payload", () => {
  assert.deepEqual(buildThemeModePatch("dark"), {
    ui: { theme_mode: "dark" },
  });
});

test("buildAutoOcrPatch returns expected payload", () => {
  assert.deepEqual(buildAutoOcrPatch(false), {
    documents: { auto_ocr: false },
  });
});

test("buildNotesPreferencesPatch returns per-user note preferences", () => {
  assert.deepEqual(buildNotesPreferencesPatch({ notes_writing_width: "wide", notes_tts_voice: "sleepy" }), {
    ui: { notes_writing_width: "wide", notes_tts_voice: "sleepy" },
  });
});

test("normalizeNoteTextReplacements validates and deduplicates shortcuts", () => {
  assert.deepEqual(normalizeNoteTextReplacements([
    { shortcut: " MFG ", replacement: " Mit freundlichen Grüßen " },
    { shortcut: "MFG", replacement: "Duplikat" },
    { shortcut: "zu kurz mit leerzeichen", replacement: "Ungültig" },
  ]), [
    { shortcut: "MFG", replacement: "Mit freundlichen Grüßen", enabled: true },
  ]);
});

test("buildAutoTaggingPatch returns expected payload", () => {
  assert.deepEqual(buildAutoTaggingPatch(true), {
    documents: { auto_tagging: true },
  });
});

test("buildAutoOpenImportInboxPatch returns expected payload", () => {
  assert.deepEqual(buildAutoOpenImportInboxPatch(true), {
    documents: { auto_open_import_inbox: true },
  });
});

test("buildSidebarShowDossiersPatch returns expected payload", () => {
  assert.deepEqual(buildSidebarShowDossiersPatch(false), {
    ui: { sidebar_show_dossiers: false },
  });
});

test("buildSidebarShowLernraumPatch returns expected payload", () => {
  assert.deepEqual(buildSidebarShowLernraumPatch(false), {
    ui: { sidebar_show_lernraum: false },
  });
});

test("buildSidebarMaxFoldersPatch clamps the visible folder count", () => {
  assert.deepEqual(buildSidebarMaxFoldersPatch(8), {
    ui: { sidebar_max_folders: 8 },
  });
  assert.deepEqual(buildSidebarMaxFoldersPatch(99), {
    ui: { sidebar_max_folders: 50 },
  });
});

test("buildSortOrderPatch returns expected payload", () => {
  assert.deepEqual(buildSortOrderPatch("last_opened"), {
    documents: { sort_order: "last_opened" },
  });
});

test("buildRecentImportWindowPatch returns expected payload", () => {
  assert.deepEqual(buildRecentImportWindowPatch(12), {
    documents: { recent_import_window_hours: 12 },
  });
});

test("buildTrashRetentionPatch returns expected payload", () => {
  assert.deepEqual(buildTrashRetentionPatch(30), {
    documents: { trash_retention_days: 30 },
  });
});
