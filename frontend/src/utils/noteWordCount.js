/** Count only selected ranges, including multi-cell selections, without reading the whole note. */
export function selectedWordCount(state) {
  if (!state?.selection || state.selection.empty) return null;
  const text = state.selection.ranges.map(({ $from, $to }) =>
    state.doc.textBetween($from.pos, $to.pos, ' ', ' '),
  ).join(' ').trim();
  return text ? text.split(/\s+/u).length : 0;
}

export function wordCountLabel(total, selected = null) {
  if (selected !== null) return `${selected} von ${total} ${total === 1 ? 'Wort' : 'Wörtern'}`;
  return `${total} ${total === 1 ? 'Wort' : 'Wörter'}`;
}
