export function dossierDocumentCardTitle(document) {
  const rawTitle = String(document?.title || 'Dokument').trim() || 'Dokument';
  return {
    display: rawTitle.replace(/\.pdf$/i, '').trim() || 'Dokument',
    full: rawTitle,
  };
}

export function dossierDocumentPageLabel(document) {
  const pageCount = Number(document?.page_count || 0);
  if (pageCount > 0) return `${pageCount} ${pageCount === 1 ? 'Seite' : 'Seiten'}`;
  return document?.document_date || '';
}
