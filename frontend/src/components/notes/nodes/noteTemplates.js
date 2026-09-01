/*
 * Vorlagen-Presets für den Vorlagenfeld-Block (templateBox). Ein Preset legt
 * Titel, Farbvariante und die anfänglichen Feldzeilen (Label + Platzhalter) fest.
 * Die Platzhalter sind reines Chrome: solange ein Feld leer bleibt, erscheint der
 * Hinweistext, landet aber NICHT im gespeicherten Notiz-JSON.
 */

export const NOTE_TEMPLATE_PRESETS = [
  {
    key: 'gespraech',
    label: 'Gesprächsnotiz',
    desc: 'Datum · Teilnehmer · Thema · Ergebnis',
    chip: '▤',
    variant: 'gespraech',
    color: 'teal',
    title: 'Gesprächsnotiz',
    terms: ['gespräch', 'gesprächsnotiz', 'notiz', 'meeting', 'besprechung', 'vorlage', 'template'],
    fields: [
      { label: 'Datum', hint: 'tt.mm.jjjj' },
      { label: 'Teilnehmer', hint: 'Wer war dabei?' },
      { label: 'Thema', hint: 'Worum ging es?' },
      { label: 'Ergebnis', hint: 'Was wurde vereinbart?' },
    ],
  },
];

// Wählbare Tönungen des Vorlagen-Blocks. Bewusst harmonisch zu den Callout-Farben.
export const NOTE_TEMPLATE_COLORS = [
  { key: 'teal', label: 'Teal', hex: '#0f6e56' },
  { key: 'blau', label: 'Blau', hex: '#5b6fb8' },
  { key: 'gruen', label: 'Grün', hex: '#2f855a' },
  { key: 'bernstein', label: 'Bernstein', hex: '#b7791f' },
  { key: 'rose', label: 'Rosé', hex: '#b5497a' },
  { key: 'neutral', label: 'Neutral', hex: '#5f6b70' },
];

// Attribute für eine frisch hinzugefügte (noch unbenannte) Feldzeile. Der Hint
// sorgt dafür, dass auch neue Zeilen einen Wert-Platzhalter zeigen.
export function newTemplateFieldAttrs() {
  return { label: '', hint: 'Wert' };
}

const COLOR_BY_KEY = new Map(NOTE_TEMPLATE_COLORS.map((color) => [color.key, color]));

export function normalizeTemplateColor(key) {
  return COLOR_BY_KEY.has(key) ? key : 'teal';
}

export function templateColorHex(key) {
  return (COLOR_BY_KEY.get(key) || COLOR_BY_KEY.get('teal')).hex;
}

const PRESET_BY_KEY = new Map(NOTE_TEMPLATE_PRESETS.map((preset) => [preset.key, preset]));

export function noteTemplatePreset(key) {
  return PRESET_BY_KEY.get(key) || null;
}

export const NOTE_TEMPLATE_VARIANTS = ['note', 'gespraech'];

export function normalizeTemplateVariant(value) {
  return NOTE_TEMPLATE_VARIANTS.includes(value) ? value : 'note';
}

export default NOTE_TEMPLATE_PRESETS;
