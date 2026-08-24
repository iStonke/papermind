function validDate(value) {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime()) ? date : null;
}

function localDayKey(date) {
  if (!date) return 'unknown';
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function groupLabel(date, now) {
  if (!date) return 'Ohne Erstellungsdatum';
  const todayKey = localDayKey(now);
  if (localDayKey(date) === todayKey) return 'Heute';

  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  if (localDayKey(date) === localDayKey(yesterday)) return 'Gestern';

  return new Intl.DateTimeFormat('de-DE', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: 'numeric' }),
  }).format(date);
}

/**
 * Gruppiert eine bereits sortierte Notizenliste nach dem lokalen Kalendertag
 * ihrer Erstellung. Die Reihenfolge innerhalb der Gruppen bleibt erhalten.
 */
export function groupNotesByCreationDay(notes, now = new Date()) {
  const groups = new Map();
  for (const note of notes || []) {
    const date = validDate(note?.created_at || note?.updated_at);
    const key = localDayKey(date);
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        label: groupLabel(date, now),
        order: date
          ? new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
          : Number.NEGATIVE_INFINITY,
        notes: [],
      });
    }
    groups.get(key).notes.push(note);
  }
  return [...groups.values()].sort((a, b) => b.order - a.order);
}
