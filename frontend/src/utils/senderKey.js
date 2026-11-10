/** Vergleichsschlüssel für Absender-/Korrespondentennamen: ohne Groß-/Kleinschreibung, Leer- und Satzzeichen. */
export function senderKey(name) {
  return String(name || '').normalize('NFKC').toLocaleLowerCase('de-DE').replace(/[^\p{L}\p{N}]/gu, '');
}
