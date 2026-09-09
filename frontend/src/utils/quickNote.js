export const QUICK_NOTE_TITLE_MAX_LENGTH = 500;

function paragraphFromLine(line) {
  const text = String(line || '').trim();
  return text
    ? { type: 'paragraph', content: [{ type: 'text', text }] }
    : { type: 'paragraph' };
}

/**
 * Wandelt die kompakte Dashboard-Eingabe in das kanonische Notizformat um.
 * Die erste Zeile wird zum Titel, alle weiteren Zeilen zu ProseMirror-Absätzen.
 */
export function buildQuickNotePayload(value) {
  const normalized = String(value || '').replace(/\r\n?/g, '\n').trim();
  if (!normalized) return null;

  const [titleLine, ...bodyLines] = normalized.split('\n');
  return {
    title: titleLine.trim().slice(0, QUICK_NOTE_TITLE_MAX_LENGTH),
    body_json: {
      type: 'doc',
      content: bodyLines.length
        ? bodyLines.map(paragraphFromLine)
        : [{ type: 'paragraph' }],
    },
  };
}
