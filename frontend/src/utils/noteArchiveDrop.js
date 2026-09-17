export const MAX_NOTE_ARCHIVE_BYTES = 100 * 1024 * 1024;

export function isNoteArchiveFile(file) {
  const name = String(file?.name || '').toLocaleLowerCase('de-DE');
  const type = String(file?.type || '').toLocaleLowerCase('de-DE');
  return name.endsWith('.papermind.json') || (name.endsWith('.json') && type === 'application/json');
}

export function selectNoteArchiveFiles(files) {
  return Array.from(files || []).filter(isNoteArchiveFile);
}
