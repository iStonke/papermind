/*
 * Lernmarkierungen: drei feste, nicht konfigurierbare Bedeutungen. `key` ist der
 * Wert in der API/DB, `hex` die Darstellungsfarbe im PDF (gleiche Tonalität wie
 * die Lesemodus-Palette, damit beide Ebenen ruhig nebeneinander wirken).
 */
export const LEARN_HIGHLIGHT_COLORS = Object.freeze([
  { key: 'important', label: 'Wichtig', hex: '#FAC775' },
  { key: 'definition', label: 'Definition', hex: '#B5D4F4' },
  { key: 'unclear', label: 'Unklar', hex: '#F5A3A3' },
]);

const BY_KEY = new Map(LEARN_HIGHLIGHT_COLORS.map((entry) => [entry.key, entry]));
const BY_HEX = new Map(LEARN_HIGHLIGHT_COLORS.map((entry) => [entry.hex.toLowerCase(), entry]));

export function learnHighlightByKey(key) {
  return BY_KEY.get(String(key || '')) || null;
}

export function learnHighlightByHex(hex) {
  return BY_HEX.get(String(hex || '').trim().toLowerCase()) || null;
}
