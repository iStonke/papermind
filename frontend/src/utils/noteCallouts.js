export const NOTE_CALLOUT_OPTIONS = Object.freeze([
  {
    value: 'info',
    label: 'Information',
    glyph: 'i',
    description: 'Ergänzende Information hervorheben',
    terms: ['information', 'info', 'hinweis', 'wissen'],
  },
  {
    value: 'important',
    label: 'Wichtig',
    glyph: '!',
    description: 'Zentrale Information hervorheben',
    terms: ['wichtig', 'hinweis', 'achtung'],
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
  {
    value: 'prompt',
    label: 'KI-Prompt',
    glyph: '✦',
    description: 'Prompt für die Schreibassistenz festhalten',
    terms: ['ki', 'ai', 'prompt', 'anweisung', 'schreibauftrag'],
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
