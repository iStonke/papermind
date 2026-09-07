function timestamp(value) {
  const parsed = value ? new Date(value).getTime() : 0;
  return Number.isFinite(parsed) ? parsed : 0;
}

export function sortNoteItems(items, mode = 'updated', reversed = false) {
  const direction = reversed ? -1 : 1;
  return [...items].sort((a, b) => {
    if (mode === 'title') return direction * String(a.title || '').localeCompare(String(b.title || ''), 'de-DE');
    const date = note => mode === 'created' ? note.created_at || note.updated_at : note.updated_at;
    return direction * (timestamp(date(b)) - timestamp(date(a)));
  });
}
