import test from "node:test";
import assert from "node:assert/strict";

import {
  buildAutoOpenImportInboxPatch,
  buildAutoOcrPatch,
  buildAutoTaggingPatch,
  buildColorVariantPatch,
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

test("buildColorVariantPatch returns expected payload", () => {
  assert.deepEqual(buildColorVariantPatch("forest"), {
    ui: { color_variant: "forest" },
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

test("buildAutoOpenImportInboxPatch returns expected payload", () => {
  assert.deepEqual(buildAutoOpenImportInboxPatch(true), {
    documents: { auto_open_import_inbox: true },
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
