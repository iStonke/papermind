export const NOTE_CALLOUT_OPTIONS = Object.freeze([
  {
    value: 'important',
    label: 'Wichtig',
    glyph: '!',
    description: 'Zentrale Information hervorheben',
    terms: ['wichtig', 'hinweis', 'achtung', 'info'],
  },
  {
    value: 'question',
    label: 'Frage',
    glyph: '?',
    description: 'Offene Frage festhalten',
    terms: ['frage', 'offen', 'prüfen', 'unklar'],
  },
  {
    value: 'decision',
    label: 'Entscheidung',
    glyph: '✓',
    description: 'Entscheidung dokumentieren',
    terms: ['entscheidung', 'beschluss', 'ergebnis'],
  },
  {
    value: 'deadline',
    label: 'Frist',
    glyph: '◷',
    description: 'Termin oder Frist markieren',
    terms: ['frist', 'termin', 'datum', 'deadline'],
  },
  {
    value: 'source',
    label: 'Fundstelle',
    glyph: '⌖',
    description: 'Beleg oder Fundstelle hervorheben',
    terms: ['fundstelle', 'quelle', 'beleg', 'dokument'],
  },
]);

export function normalizeNoteCalloutKind(value) {
  const normalized = String(value || '').toLowerCase();
  return NOTE_CALLOUT_OPTIONS.some((option) => option.value === normalized)
    ? normalized
    : 'important';
}

export function noteCalloutMeta(value) {
  const kind = normalizeNoteCalloutKind(value);
  return NOTE_CALLOUT_OPTIONS.find((option) => option.value === kind) || NOTE_CALLOUT_OPTIONS[0];
}
