const metadataLabel = /(?:^|[.;\n]\s*)(?:Absender|Aussteller|Thema|Betreff|Dokumenttyp|Dokumentdatum|Datum|Betrag|Währung|Tags)\s*:/giu;
const comparable = value => String(value || '').toLocaleLowerCase('de-DE').replace(/[^\p{L}\p{N}]+/gu, ' ').trim();

// Only automatic notes pass through this filter. Manual notes are preserved.
export function usefulAnalysisNote(value, metadata = {}) {
  metadata ||= {};
  const text = String(value || '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/gu, '').trim().slice(0, 10000);
  if (!text) return '';
  const characters = text.replace(/\s/gu, '');
  const readable = characters.match(/[\p{L}\p{N}]/gu)?.length || 0;
  if (readable / Math.max(1, characters.length) < .55 || /[�]{2,}|([%&#?])\1{3,}/u.test(text)) return '';
  const labels = [...text.matchAll(metadataLabel)];
  if (labels.length >= 2 && labels[0].index === 0) return '';
  if (labels.length === 1 && labels[0].index === 0 && !/[.!?\n]\s+\p{L}/u.test(text.slice(labels[0][0].length))) return '';
  const normalized = comparable(text);
  const values = [metadata.title, metadata.subject, metadata.document_type, metadata.category, metadata.sender_raw, metadata.date];
  const unlabelled = labels.length === 1 && labels[0].index === 0 ? comparable(text.slice(labels[0][0].length)) : normalized;
  if (values.some(value => comparable(value) && [normalized, unlabelled].includes(comparable(value)))) return '';
  return text;
}

export function importAnalysisScope(meta, pages) {
  const count = Number(meta?.pages_analyzed);
  if (!Number.isInteger(count) || count < 1) return '';
  const total = Number(meta.pages_total) || pages.length;
  const refs = new Set(meta.page_refs || []);
  const numbers = pages.flatMap((page, index) => refs.has(`${page.sourceFileId}:${page.pageIndex}`) ? [index + 1] : []);
  const selection = numbers.length === count ? `Seite${count === 1 ? '' : 'n'} ${numbers.join(', ')}` : `${count} Seite${count === 1 ? '' : 'n'}`;
  return `Letzte Auswertung: ${selection} (${count} von ${total}).${count < total ? ' Weitere Seiten wurden nicht berücksichtigt.' : ''}`;
}
