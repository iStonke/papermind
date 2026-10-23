// A document can contain both scans and selected PDFs after appending or moving
// pages. Retention therefore follows each source's origin.
export function scannerDraft(draft) {
  if (!draft) return null;
  const metadata = new Map(draft.sourceMeta || []);
  const documents = draft.documents.map(doc => ({ ...doc,
    pages: doc.pages.filter(page => metadata.get(page.sourceFileId)?.sourceType === 'scanner'),
  })).filter(doc => doc.pages.length);
  if (!documents.length) return null;
  const used = new Set(documents.flatMap(doc => doc.pages.map(page => page.sourceFileId)));
  return { ...draft, documents, sourceMeta: (draft.sourceMeta || []).filter(([id]) => used.has(id)),
    files: (draft.files || []).filter(([id]) => used.has(id)) };
}

export function scannerPageCount(draft) {
  return (scannerDraft(draft)?.documents || []).reduce((sum, doc) => sum + doc.pages.length, 0);
}
