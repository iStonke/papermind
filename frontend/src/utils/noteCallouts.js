export const NOTE_CALLOUT_OPTIONS = Object.freeze([
  {
    value: 'info',
    label: 'Information',
    glyph: 'i',
    icon: 'callout-info',
    description: 'Ergänzende Information hervorheben',
    terms: ['information', 'info', 'hinweis', 'wissen'],
  },
  {
    value: 'important',
    label: 'Wichtig',
    glyph: '!',
    icon: 'callout-important',
    description: 'Zentrale Information hervorheben',
    terms: ['wichtig', 'hinweis', 'achtung'],
  },
  {
    value: 'question',
    label: 'Frage',
    glyph: '?',
    icon: 'callout-question',
    description: 'Offene Frage festhalten',
    terms: ['frage', 'offen', 'prüfen', 'unklar'],
  },
  {
    value: 'decision',
    label: 'Entscheidung',
    glyph: '✓',
    icon: 'callout-decision',
    description: 'Entscheidung dokumentieren',
    terms: ['entscheidung', 'beschluss', 'ergebnis'],
  },
  {
    value: 'prompt',
    label: 'KI-Prompt',
    glyph: '✦',
    icon: 'callout-prompt',
    description: 'Prompt für die Schreibassistenz festhalten',
    terms: ['ki', 'ai', 'prompt', 'anweisung', 'schreibauftrag'],
  },
]);

export function normalizeNoteCalloutKind(value) {
  const normalized = String(value || '').toLowerCase();
  // Retired kinds retain their content as ordinary information blocks.
  if (['deadline', 'source'].includes(normalized)) return 'info';
  return NOTE_CALLOUT_OPTIONS.some((option) => option.value === normalized)
    ? normalized
    : 'important';
}

export function noteCalloutMeta(value) {
  const kind = normalizeNoteCalloutKind(value);
  return NOTE_CALLOUT_OPTIONS.find((option) => option.value === kind) || NOTE_CALLOUT_OPTIONS[0];
}
