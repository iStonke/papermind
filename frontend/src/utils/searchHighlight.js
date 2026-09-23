// Zerlegt Text in Treffer-/Nicht-Treffer-Teile für eine sichere Hervorhebung
// (ohne v-html). Mehrwort-Suchen markieren jedes Wort; längste Begriffe zuerst.
export function highlightParts(value, query) {
  const text = String(value || '');
  const terms = [...new Set(
    String(query || '').split(/\s+/).map((term) => term.trim()).filter(Boolean),
  )].sort((a, b) => b.length - a.length);
  if (!terms.length) return [{ text, match: false }];
  const escapedTerms = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`(${escapedTerms.join('|')})`, 'giu');
  const normalizedTerms = new Set(terms.map((term) => term.toLocaleLowerCase('de-DE')));
  return text.split(pattern).filter(Boolean).map((part) => ({
    text: part,
    match: normalizedTerms.has(part.toLocaleLowerCase('de-DE')),
  }));
}

// Schneidet einen Textauszug so zu, dass der erste Treffer nicht am Rand
// verschwindet: vor dem Treffer bleiben höchstens `lead` Zeichen stehen.
export function centerOnMatch(value, query, lead = 48) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  const terms = String(query || '').split(/\s+/).filter(Boolean);
  if (!text || !terms.length) return text;
  const lower = text.toLocaleLowerCase('de-DE');
  const positions = terms
    .map((term) => lower.indexOf(term.toLocaleLowerCase('de-DE')))
    .filter((index) => index >= 0);
  if (!positions.length) return text;
  const first = Math.min(...positions);
  if (first <= lead) return text;
  let start = first - lead;
  const space = text.indexOf(' ', start);
  if (space > -1 && space < first) start = space + 1;
  const trimmed = text.slice(start).replace(/^[…\s]+/, '');
  return `…${trimmed}`;
}
