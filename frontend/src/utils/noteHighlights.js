export const NOTE_HIGHLIGHT_COLORS = Object.freeze([
  Object.freeze({ value: 'yellow', label: 'Gelb', background: '#fde68a' }),
  Object.freeze({ value: 'green', label: 'Grün', background: '#bbf7d0' }),
  Object.freeze({ value: 'blue', label: 'Blau', background: '#bfdbfe' }),
  Object.freeze({ value: 'pink', label: 'Rosa', background: '#fbcfe8' }),
  Object.freeze({ value: 'purple', label: 'Violett', background: '#e9d5ff' }),
]);

const HIGHLIGHT_BY_VALUE = new Map(
  NOTE_HIGHLIGHT_COLORS.map((color) => [color.value, color]),
);

export function normalizeNoteHighlightColor(value, fallback = 'yellow') {
  const normalized = String(value || '').trim().toLowerCase();
  if (HIGHLIGHT_BY_VALUE.has(normalized)) return normalized;
  return HIGHLIGHT_BY_VALUE.has(fallback) ? fallback : 'yellow';
}

export function noteHighlightMeta(value) {
  return HIGHLIGHT_BY_VALUE.get(normalizeNoteHighlightColor(value))
    || NOTE_HIGHLIGHT_COLORS[0];
}

export function noteHighlightInlineStyle(value) {
  const { background } = noteHighlightMeta(value);
  return `background-color: ${background}; color: #172126;`;
}
