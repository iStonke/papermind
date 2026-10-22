function pageCount(value) {
  const count = Number(value);
  return Number.isFinite(count) ? Math.max(0, Math.floor(count)) : 0;
}

// The server can still list a source restored from a local draft. Its original
// pages must not be counted again (or resurrect pages removed from the draft).
export function importAvailability({ pendingCount = 0, items = [], documents = [], availableDocuments = [] } = {}) {
  const stagedPages = documents.flatMap(document => document.pages || []);
  const savedPages = availableDocuments.flatMap(document => document.pages || []);
  const stagedSources = new Set([...stagedPages, ...savedPages].map(page => page.sourceFileId));
  const seen = new Set();
  let overlap = 0;
  for (const item of items) {
    if (seen.has(item.source_file_id)) continue;
    seen.add(item.source_file_id);
    if (stagedSources.has(item.source_file_id)) overlap += pageCount(item.page_count);
  }
  const pendingPages = Math.max(0, pageCount(pendingCount) - overlap);
  return { pendingPages, totalPages: stagedPages.length + savedPages.length + pendingPages };
}

export function shouldLoadInboxIntoOpenImport({ open, stagedPages, scannerActive }) {
  return Boolean(open && (stagedPages > 0 || scannerActive));
}
