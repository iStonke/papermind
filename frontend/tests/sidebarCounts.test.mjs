import test from "node:test";
import assert from "node:assert/strict";

import { createEmptyCounts, normalizeCounts } from "../src/utils/sidebarCounts.js";

test("createEmptyCounts includes library counters", () => {
  assert.equal(createEmptyCounts().favorites_count, 0);
  assert.equal(createEmptyCounts().trash_count, 0);
});

test("normalizeCounts preserves favorites and trash counts", () => {
  const normalized = normalizeCounts({
    all_documents: 7,
    favorites_count: 3,
    trash_count: 2,
    imports: { recent_total: 1 },
  });

  assert.equal(normalized.all_documents, 7);
  assert.equal(normalized.favorites_count, 3);
  assert.equal(normalized.trash_count, 2);
  assert.equal(normalized.imports.recent_total, 1);
});
