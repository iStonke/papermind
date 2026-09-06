import { readFile } from 'node:fs/promises';

// Legacy structural checks follow the editor's owned modules rather than
// requiring every feature to live in NoteEditor.vue. Behavior is tested separately.
export async function readNoteEditorSource() {
  const visited = new Set();
  async function read(url) {
    if (visited.has(url.href)) return '';
    visited.add(url.href);
    const source = await readFile(url, 'utf8');
    const dependencies = [...source.matchAll(/from ['"]([^'"]+)['"]/g), ...source.matchAll(/<style[^>]*src=['"]([^'"]+)['"]/g)]
      .map((match) => match[1])
      .filter((path) => path.startsWith('./') && !path.startsWith('./nodes/') && !path.startsWith('./extensions/'));
    const children = [];
    for (const path of dependencies) children.push(await read(new URL(path, url)));
    return [source, ...children].join('\n');
  }
  return read(new URL('../../src/components/notes/NoteEditor.vue', import.meta.url));
}
