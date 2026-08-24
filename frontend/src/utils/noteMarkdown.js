const BULLET_ITEM = /^\s*[-*+]\s+(.+?)\s*$/;
const ORDERED_ITEM = /^\s*(\d+)[.)]\s+(.+?)\s*$/;
const TABLE_SEPARATOR_CELL = /^:?-{3,}:?$/;

function splitMarkdownTableRow(value) {
  const source = String(value || '').trim().replace(/^\|/, '').replace(/\|$/, '');
  const cells = [];
  let cell = '';
  let escaped = false;
  let codeFenceLength = 0;
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (escaped) {
      cell += char;
      escaped = false;
      continue;
    }
    if (char === '\\') {
      escaped = true;
      continue;
    }
    if (char === '`') {
      let run = 1;
      while (source[index + run] === '`') run += 1;
      codeFenceLength = codeFenceLength === run ? 0 : (codeFenceLength ? codeFenceLength : run);
      cell += '`'.repeat(run);
      index += run - 1;
      continue;
    }
    if (char === '|' && !codeFenceLength) {
      cells.push(cell.trim());
      cell = '';
      continue;
    }
    cell += char;
  }
  if (escaped) cell += '\\';
  cells.push(cell.trim());
  return cells;
}

function isMarkdownTableStart(lines, index) {
  if (index + 1 >= lines.length || !lines[index].includes('|')) return false;
  const header = splitMarkdownTableRow(lines[index]);
  const separator = splitMarkdownTableRow(lines[index + 1]);
  return header.length >= 2
    && separator.length === header.length
    && separator.every((cell) => TABLE_SEPARATOR_CELL.test(cell.replace(/\s+/g, '')));
}

export function parseMarkdownInline(value) {
  const text = String(value || '');
  const segments = [];
  const pattern = /(\*\*([^*\n]+)\*\*|__([^_\n]+)__|`([^`\n]+)`|\*([^*\n]+)\*|_([^_\n]+)_)/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) segments.push({ text: text.slice(cursor, match.index) });
    if (match[2] != null || match[3] != null) {
      segments.push({ text: match[2] ?? match[3], bold: true });
    } else if (match[4] != null) {
      segments.push({ text: match[4], code: true });
    } else {
      segments.push({ text: match[5] ?? match[6], italic: true });
    }
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
  return segments.length ? segments : [{ text }];
}

export function parseNoteMarkdown(value) {
  const lines = String(value || '').replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    if (!lines[index].trim()) {
      index += 1;
      continue;
    }

    if (isMarkdownTableStart(lines, index)) {
      const headerCells = splitMarkdownTableRow(lines[index]).map(parseMarkdownInline);
      const columnCount = headerCells.length;
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes('|')) {
        const cells = splitMarkdownTableRow(lines[index]);
        if (cells.length !== columnCount) break;
        rows.push(cells.map(parseMarkdownInline));
        index += 1;
      }
      blocks.push({ type: 'table', header: headerCells, rows });
      continue;
    }

    const bullet = BULLET_ITEM.exec(lines[index]);
    if (bullet) {
      const items = [];
      while (index < lines.length) {
        const item = BULLET_ITEM.exec(lines[index]);
        if (!item) break;
        items.push(parseMarkdownInline(item[1]));
        index += 1;
      }
      blocks.push({ type: 'bulletList', items });
      continue;
    }

    const ordered = ORDERED_ITEM.exec(lines[index]);
    if (ordered) {
      const items = [];
      const start = Number(ordered[1]) || 1;
      while (index < lines.length) {
        const item = ORDERED_ITEM.exec(lines[index]);
        if (!item) break;
        items.push(parseMarkdownInline(item[2]));
        index += 1;
      }
      blocks.push({ type: 'orderedList', start, items });
      continue;
    }

    const paragraphLines = [];
    while (
      index < lines.length
      && lines[index].trim()
      && !BULLET_ITEM.test(lines[index])
      && !ORDERED_ITEM.test(lines[index])
      && !isMarkdownTableStart(lines, index)
    ) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }
    blocks.push({
      type: 'paragraph',
      segments: parseMarkdownInline(paragraphLines.join(' ')),
    });
  }

  return blocks;
}

function inlineToTipTap(segments) {
  return segments
    .filter((segment) => segment.text)
    .map((segment) => {
      const marks = [];
      if (segment.bold) marks.push({ type: 'bold' });
      if (segment.italic) marks.push({ type: 'italic' });
      if (segment.code) marks.push({ type: 'code' });
      return {
        type: 'text',
        text: segment.text,
        ...(marks.length ? { marks } : {}),
      };
    });
}

export function noteMarkdownToTipTap(value) {
  return parseNoteMarkdown(value).map((block) => {
    if (block.type === 'paragraph') {
      const content = inlineToTipTap(block.segments);
      return { type: 'paragraph', ...(content.length ? { content } : {}) };
    }
    if (block.type === 'table') {
      const tableCell = (segments, type) => {
        const content = inlineToTipTap(segments);
        return {
          type,
          content: [{ type: 'paragraph', ...(content.length ? { content } : {}) }],
        };
      };
      return {
        type: 'table',
        content: [
          { type: 'tableRow', content: block.header.map((segments) => tableCell(segments, 'tableHeader')) },
          ...block.rows.map((row) => ({
            type: 'tableRow',
            content: row.map((segments) => tableCell(segments, 'tableCell')),
          })),
        ],
      };
    }
    return {
      type: block.type,
      ...(block.type === 'orderedList' ? { attrs: { start: block.start } } : {}),
      content: block.items.map((segments) => {
        const content = inlineToTipTap(segments);
        return {
          type: 'listItem',
          content: [{ type: 'paragraph', ...(content.length ? { content } : {}) }],
        };
      }),
    };
  });
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function inlineToHtml(segments) {
  return segments.map((segment) => {
    let value = escapeHtml(segment.text);
    if (segment.code) value = `<code>${value}</code>`;
    if (segment.italic) value = `<em>${value}</em>`;
    if (segment.bold) value = `<strong>${value}</strong>`;
    return value;
  }).join('');
}

export function noteMarkdownToSafeHtml(value) {
  return parseNoteMarkdown(value).map((block) => {
    if (block.type === 'paragraph') return `<p>${inlineToHtml(block.segments)}</p>`;
    if (block.type === 'table') {
      const header = block.header.map((segments) => `<th>${inlineToHtml(segments)}</th>`).join('');
      const rows = block.rows.map((row) => (
        `<tr>${row.map((segments) => `<td>${inlineToHtml(segments)}</td>`).join('')}</tr>`
      )).join('');
      return `<div class="table-wrap"><table><thead><tr>${header}</tr></thead><tbody>${rows}</tbody></table></div>`;
    }
    const tag = block.type === 'orderedList' ? 'ol' : 'ul';
    const start = tag === 'ol' && block.start !== 1 ? ` start="${block.start}"` : '';
    const items = block.items.map((segments) => `<li>${inlineToHtml(segments)}</li>`).join('');
    return `<${tag}${start}>${items}</${tag}>`;
  }).join('');
}
