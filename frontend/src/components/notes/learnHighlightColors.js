/*
 * Lernmarkierungen: drei feste, nicht konfigurierbare Bedeutungen. `key` ist der
 * Wert in der API/DB, `hex` die Darstellungsfarbe im PDF (gleiche Tonalität wie
 * die Lesemodus-Palette, damit beide Ebenen ruhig nebeneinander wirken).
 *
 * `markerKind` koppelt an den Lernbereich: Wird markierter Text als Zitat in die
 * Notiz übernommen, trägt das Zitat diesen Lern-Marker. Die Nachbereitung leitet
 * daraus den Kartentyp ab (lernen/fakt → Fakt-Karte mit dem Zitat als Antwort,
 * warum → Verständnis-Karte mit dem Zitat als Frage). `autoQuote`: Diese
 * Bedeutung übernimmt die Stelle sofort als offene Frage in die Notiz.
 */
export const LEARN_HIGHLIGHT_COLORS = Object.freeze([
  { key: 'important', label: 'Wichtig', hex: '#FAC775', markerKind: 'lernen' },
  { key: 'definition', label: 'Definition', hex: '#B5D4F4', markerKind: 'fakt' },
  { key: 'unclear', label: 'Unklar', hex: '#F5A3A3', markerKind: 'warum', autoQuote: true },
]);

const BY_KEY = new Map(LEARN_HIGHLIGHT_COLORS.map((entry) => [entry.key, entry]));
const BY_HEX = new Map(LEARN_HIGHLIGHT_COLORS.map((entry) => [entry.hex.toLowerCase(), entry]));

export function learnHighlightByKey(key) {
  return BY_KEY.get(String(key || '')) || null;
}

export function learnHighlightByHex(hex) {
  return BY_HEX.get(String(hex || '').trim().toLowerCase()) || null;
}
