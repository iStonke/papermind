export function normalizeNoteImageWidth(value) {
  const width = Number(value);
  if (!Number.isFinite(width)) return 100;
  return Math.round(Math.min(100, Math.max(30, width)));
}
