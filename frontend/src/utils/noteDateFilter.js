export function noteMatchesDateRange(note, range, now = new Date()) {
  if (!range) return true;
  const date = new Date(note.updated_at);
  if (!Number.isFinite(date.getTime())) return false;
  const end = new Date(now);
  end.setHours(24, 0, 0, 0);
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const days = { today: 1, last_7_days: 7, last_30_days: 30 }[range];
  if (!days) return true;
  start.setDate(start.getDate() - days + 1);
  return date >= start && date < end;
}
