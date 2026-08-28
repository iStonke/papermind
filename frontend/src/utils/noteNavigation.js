function noteNodeSize(node) {
  if (!node || typeof node !== 'object') return 0;
  if (node.type === 'text') return String(node.text || '').length;
  const contentSize = Array.isArray(node.content)
    ? node.content.reduce((size, child) => size + noteNodeSize(child), 0)
    : 0;
  return node.type === 'doc' ? contentSize : contentSize + 2;
}

function noteNodeText(node) {
  if (!node || typeof node !== 'object') return '';
  if (node.type === 'text') return String(node.text || '');
  return Array.isArray(node.content) ? node.content.map(noteNodeText).join('') : '';
}

/**
 * Erzeugt eine klickbare Gliederung samt ProseMirror-Positionen aus dem
 * gespeicherten TipTap-JSON. Der Notiztitel ist H1; deshalb beginnt die
 * eigentliche Inhaltsgliederung bei H2.
 */
export function extractNoteOutline(bodyJson) {
  if (!bodyJson || bodyJson.type !== 'doc') return [];
  const items = [];

  function visit(node, position, isDocument = false) {
    if (node?.type === 'heading') {
      const level = Number(node.attrs?.level) || 2;
      const text = noteNodeText(node).replace(/\s+/g, ' ').trim();
      if (text && level >= 2 && level <= 4) {
        items.push({
          key: `${position}:${level}:${text}`,
          level,
          text,
          position,
        });
      }
    }

    let childPosition = isDocument ? position : position + 1;
    for (const child of node?.content || []) {
      visit(child, childPosition, false);
      childPosition += noteNodeSize(child);
    }
  }

  visit(bodyJson, 0, true);
  return items;
}

export function nextWrappedIndex(currentIndex, count, direction = 1) {
  const total = Math.max(0, Number(count) || 0);
  if (!total) return -1;
  const current = Number.isInteger(currentIndex) ? currentIndex : -1;
  return ((current + direction) % total + total) % total;
}
