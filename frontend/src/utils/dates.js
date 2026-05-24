/**
 * Formatiert einen ISO-Datetime-String als lesbares deutsches Datum mit Uhrzeit.
 * Gibt '-' zurück wenn der Wert fehlt oder ungültig ist.
 */
export function formatDateTime(value) {
  if (!value) {
    return '-';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '-';
  }
  return new Intl.DateTimeFormat('de-DE', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(parsed);
}

/**
 * Wandelt ein ISO-Datum (YYYY-MM-DD) in das deutsche Eingabeformat (DD.MM.YYYY) um.
 * Gibt '' zurück wenn der Wert fehlt oder kein gültiges ISO-Datum ist.
 */
export function formatDocumentDateInputFromIso(value) {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return '';
  }
  const match = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return '';
  }
  return `${match[3]}.${match[2]}.${match[1]}`;
}

/**
 * Parst eine Datumseingabe im deutschen Format (DD.MM.YYYY oder D.M.YYYY).
 * Gibt { ok, iso, display } zurück:
 *   ok      – ob die Eingabe ein gültiges Datum ergibt
 *   iso     – YYYY-MM-DD (null wenn leer oder ungültig)
 *   display – bereinigter Anzeigetext
 */
export function parseDocumentDateInput(rawValue) {
  const normalized = String(rawValue || '').trim();
  if (!normalized) {
    return { ok: true, iso: null, display: '' };
  }

  const match = normalized.match(/^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$/);
  if (!match) {
    return { ok: false, iso: null, display: normalized };
  }

  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  const dateValue = new Date(year, month - 1, day);
  if (
    Number.isNaN(dateValue.getTime()) ||
    dateValue.getFullYear() !== year ||
    dateValue.getMonth() !== month - 1 ||
    dateValue.getDate() !== day
  ) {
    return { ok: false, iso: null, display: normalized };
  }

  const dd = String(day).padStart(2, '0');
  const mm = String(month).padStart(2, '0');
  return {
    ok: true,
    iso: `${year}-${mm}-${dd}`,
    display: `${dd}.${mm}.${year}`
  };
}
