function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

// ts_headline liefert <mark>-Paare. Alle anderen HTML-Tags bleiben Text.
export function formatSearchSnippet(value) {
  const snippet = String(value || '').replace(/\s+/g, ' ').trim();
  return escapeHtml(snippet)
    .replace(/&lt;mark&gt;/g, '<mark>')
    .replace(/&lt;\/mark&gt;/g, '</mark>');
}
