import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { createEmptyCounts, normalizeCounts } from "../src/utils/sidebarCounts.js";

const sidebarSource = await readFile(new URL("../src/components/AppSidebar.vue", import.meta.url), "utf8");
const settingsSource = await readFile(new URL("../src/components/SettingsDialog.vue", import.meta.url), "utf8");

test("createEmptyCounts includes library counters", () => {
  assert.equal(createEmptyCounts().favorites_count, 0);
  assert.equal(createEmptyCounts().trash_count, 0);
  assert.equal(createEmptyCounts().pending_import_inbox_count, 0);
});

test("normalizeCounts preserves favorites and trash counts", () => {
  const normalized = normalizeCounts({
    all_documents: 7,
    favorites_count: 3,
    trash_count: 2,
    pending_import_inbox_count: 4,
    imports: { recent_total: 1 },
  });

  assert.equal(normalized.all_documents, 7);
  assert.equal(normalized.favorites_count, 3);
  assert.equal(normalized.trash_count, 2);
  assert.equal(normalized.pending_import_inbox_count, 4);
  assert.equal(normalized.imports.recent_total, 1);
});

test("favorites sidebar entry is controlled only by the favorite count", () => {
  assert.match(sidebarSource, /v-if="favoritesSidebarCount > 0"/);
  assert.match(sidebarSource, /if \(favoritesSidebarCount\.value > 0\) rows\.push/);
  assert.doesNotMatch(sidebarSource, /sidebar_show_favorites/);
  assert.doesNotMatch(settingsSource, /sidebar_show_favorites/);
});
