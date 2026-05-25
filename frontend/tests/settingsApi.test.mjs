import test from "node:test";
import assert from "node:assert/strict";

import {
  buildAutoOcrPatch,
  buildAutoTaggingPatch,
  buildRecentImportWindowPatch,
  buildSortOrderPatch,
  buildThemeModePatch,
  buildTrashRetentionPatch,
} from "../src/utils/settingsApi.js";

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

test("buildAutoTaggingPatch returns expected payload", () => {
  assert.deepEqual(buildAutoTaggingPatch(true), {
    documents: { auto_tagging: true },
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
