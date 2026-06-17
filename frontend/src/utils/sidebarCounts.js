export function createEmptyCounts() {
  return {
    all_documents: 0, untagged: 0, unread_total: 0, tags_total: 0,
    favorites_count: 0, no_text_count: 0, trash_count: 0,
    imports: { imported: 0, processing: 0, ready: 0, failed: 0, recent_total: 0 },
    tags: {}, smart_folders: {}, saved_searches: {}
  };
}

export function normalizeCounts(payload) {
  const imp = payload?.imports ?? {};
  return {
    all_documents: Number(payload?.all_documents  || 0),
    untagged:      Number(payload?.untagged        || 0),
    unread_total:  Number(payload?.unread_total    || 0),
    tags_total:    Number(payload?.tags_total      || 0),
    favorites_count: Number(payload?.favorites_count || 0),
    no_text_count: Number(payload?.no_text_count   || 0),
    trash_count:   Number(payload?.trash_count     || 0),
    imports: {
      imported:     Number(imp.imported     || 0),
      processing:   Number(imp.processing   || 0),
      ready:        Number(imp.ready        || 0),
      failed:       Number(imp.failed       || 0),
      recent_total: Number(imp.recent_total || 0),
    },
    tags:          toCountMap(payload?.tags),
    smart_folders: toCountMap(payload?.smart_folders),
    saved_searches:toCountMap(payload?.saved_searches),
  };
}

function toCountMap(obj) {
  if (!obj || typeof obj !== 'object') return {};
  return Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, Number(v || 0)]));
}
