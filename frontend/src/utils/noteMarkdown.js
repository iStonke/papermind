import { normalizeNoteHref } from './noteLinks.js';

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

export function parseMarkdownInline(value, depth = 0) {
  const text = String(value || '');
  if (depth > 8) return [{ text }];
  const segments = [];
  const pattern = /\\(?<escaped>[\\`*_[\]<>])|(?<!\\)(?:\[(?<label>[^\]\n]+)\]\((?<href>[^\s)]+)\)|\*\*\*(?<strongEm>[^*\n]+)\*\*\*|\*\*(?<bold>[^*\n]+)\*\*|__(?<boldAlt>[^_\n]+)__|`(?<code>[^`\n]+)`|\*(?<italic>[^*\n]+)\*|_(?<italicAlt>[^_\n]+)_|~~(?<strike>[^~\n]+)~~)/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) segments.push({ text: text.slice(cursor, match.index) });
    const group = match.groups;
    if (group.escaped != null) segments.push({ text: group.escaped });
    else if (group.code != null) segments.push({ text: group.code, code: true });
    else {
      const content = group.label ?? group.strongEm ?? group.bold ?? group.boldAlt ?? group.italic ?? group.italicAlt ?? group.strike;
      const marks = {};
      if (group.label != null) {
        const href = normalizeNoteHref(group.href);
        if (href) marks.href = href;
      }
      if (group.strongEm != null || group.bold != null || group.boldAlt != null) marks.bold = true;
      if (group.strongEm != null || group.italic != null || group.italicAlt != null) marks.italic = true;
      if (group.strike != null) marks.strike = true;
      segments.push(...parseMarkdownInline(content, depth + 1).map((segment) => ({ ...segment, ...marks })));
    }
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
  return segments.length ? segments : [{ text }];
}

const FENCE = /^\s{0,3}(`{3,}|~{3,})([^\s]*)\s*$/;
const HEADING = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/;
const RULE = /^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$/;
const QUOTE = /^\s{0,3}> ?(.*)$/;
const LIST_ITEM = /^( *)([-*+]|\d+[.)])\s+(?:\[([ xX])\]\s+)?(.*)$/;
const CALLOUTS = Object.freeze({
  NOTE: 'info', INFO: 'info', TIP: 'info', IMPORTANT: 'important', WARNING: 'important',
  QUESTION: 'question', DECISION: 'decision', DEADLINE: 'info', SOURCE: 'info', PROMPT: 'prompt',
});

function listType(match) {
  return match[3] != null ? 'taskList' : (/^\d/.test(match[2]) ? 'orderedList' : 'bulletList');
}

export function parseNoteMarkdown(value, depth = 0) {
  const source = String(value || '').replace(/\r\n?/g, '\n');
  // Keep malformed or excessively nested model output readable without recursion overflow.
  if (depth > 24) return [{ type: 'paragraph', segments: [{ text: source }] }];
  const lines = source.split('\n');
  const blocks = [];
  let index = 0;
  const startsBlock = (i) => FENCE.test(lines[i]) || HEADING.test(lines[i]) || RULE.test(lines[i])
    || QUOTE.test(lines[i]) || LIST_ITEM.test(lines[i]) || isMarkdownTableStart(lines, i);

  while (index < lines.length) {
    if (!lines[index].trim()) { index += 1; continue; }
    const fence = FENCE.exec(lines[index]);
    if (fence) {
      const code = [];
      index += 1;
      const closing = new RegExp(`^\\s{0,3}${fence[1][0]}{${fence[1].length},}\\s*$`);
      while (index < lines.length && !closing.test(lines[index])) code.push(lines[index++]);
      if (index < lines.length) index += 1;
      // A Markdown wrapper is a transport wrapper, not a requested code element.
      if (/^(markdown|md)$/i.test(fence[2])) blocks.push(...parseNoteMarkdown(code.join('\n'), depth + 1));
      else blocks.push({ type: 'codeBlock', language: fence[2] || null, text: code.join('\n') });
      continue;
    }
    const heading = HEADING.exec(lines[index]);
    if (heading) {
      blocks.push({ type: 'heading', level: Math.min(4, Math.max(2, heading[1].length)), segments: parseMarkdownInline(heading[2]) });
      index += 1; continue;
    }
    if (RULE.test(lines[index])) { blocks.push({ type: 'horizontalRule' }); index += 1; continue; }
    if (QUOTE.test(lines[index])) {
      const quoted = [];
      while (index < lines.length && QUOTE.test(lines[index])) quoted.push(QUOTE.exec(lines[index++])[1]);
      const callout = /^\[!([A-Z]+)\]\s*(.*)$/i.exec(quoted[0]);
      const kind = callout && CALLOUTS[callout[1].toUpperCase()];
      if (kind) quoted[0] = callout[2];
      blocks.push({ type: kind ? 'callout' : 'blockquote', ...(kind ? { kind } : {}), children: parseNoteMarkdown(quoted.join('\n'), depth + 1) });
      continue;
    }
    if (isMarkdownTableStart(lines, index)) {
      const header = splitMarkdownTableRow(lines[index]).map(parseMarkdownInline);
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes('|')) {
        const cells = splitMarkdownTableRow(lines[index]);
        if (cells.length !== header.length) break;
        rows.push(cells.map(parseMarkdownInline)); index += 1;
      }
      blocks.push({ type: 'table', header, rows }); continue;
    }
    const firstItem = LIST_ITEM.exec(lines[index]);
    if (firstItem) {
      const type = listType(firstItem);
      const indent = firstItem[1].length;
      const items = [];
      while (index < lines.length) {
        const item = LIST_ITEM.exec(lines[index]);
        if (!item || item[1].length !== indent || listType(item) !== type) break;
        const body = [item[4]];
        const continuationIndent = item[0].indexOf(item[4], indent + item[2].length);
        index += 1;
        while (index < lines.length) {
          if (!lines[index].trim()) {
            let next = index + 1;
            while (next < lines.length && !lines[next].trim()) next += 1;
            const sibling = next < lines.length && LIST_ITEM.exec(lines[next]);
            if (sibling && sibling[1].length === indent && listType(sibling) === type) { index = next; break; }
            if (next >= lines.length || lines[next].search(/\S/) <= indent) break;
            body.push(''); index += 1; continue;
          }
          const spaces = lines[index].search(/\S/);
          if (spaces <= indent) break;
          body.push(lines[index].slice(Math.min(spaces, Math.max(indent + 2, continuationIndent))));
          index += 1;
        }
        items.push({ checked: item[3]?.toLowerCase() === 'x', children: parseNoteMarkdown(body.join('\n'), depth + 1) });
      }
      blocks.push({ type, ...(type === 'orderedList' ? { start: parseInt(firstItem[2], 10) || 1 } : {}), items });
      continue;
    }
    const paragraph = [lines[index++].trim()];
    while (index < lines.length && lines[index].trim() && !startsBlock(index)) paragraph.push(lines[index++].trim());
    blocks.push({ type: 'paragraph', segments: parseMarkdownInline(paragraph.join(' ')) });
  }
  return blocks;
}

function inlineToTipTap(segments) {
  return segments.filter((segment) => segment.text).map((segment) => {
    const marks = [];
    for (const type of ['bold', 'italic', 'code', 'strike']) if (segment[type]) marks.push({ type });
    if (segment.href) marks.push({ type: 'link', attrs: { href: segment.href, target: '_blank', rel: 'noopener noreferrer' } });
    return { type: 'text', text: segment.text, ...(marks.length ? { marks } : {}) };
  });
}

function blocksToTipTap(blocks) {
  return blocks.map((block) => {
    if (block.type === 'paragraph' || block.type === 'heading') {
      const content = inlineToTipTap(block.segments);
      return { type: block.type, ...(block.type === 'heading' ? { attrs: { level: block.level } } : {}), ...(content.length ? { content } : {}) };
    }
    if (block.type === 'codeBlock') return { type: 'codeBlock', attrs: { language: block.language }, ...(block.text ? { content: [{ type: 'text', text: block.text }] } : {}) };
    if (block.type === 'horizontalRule') return { type: 'horizontalRule' };
    if (block.type === 'blockquote' || block.type === 'callout') return {
      type: block.type,
      ...(block.kind ? { attrs: { kind: block.kind } } : {}),
      content: blocksToTipTap(block.children.length ? block.children : [{ type: 'paragraph', segments: [] }]),
    };
    if (block.type === 'table') {
      const cell = (segments, type) => ({ type, content: [{ type: 'paragraph', content: inlineToTipTap(segments) }] });
      return { type: 'table', content: [
        { type: 'tableRow', content: block.header.map((segments) => cell(segments, 'tableHeader')) },
        ...block.rows.map((row) => ({ type: 'tableRow', content: row.map((segments) => cell(segments, 'tableCell')) })),
      ] };
    }
    return {
      type: block.type,
      ...(block.type === 'orderedList' ? { attrs: { start: block.start } } : {}),
      content: block.items.map((item) => {
        const content = blocksToTipTap(item.children);
        // TipTap list items start with a paragraph, including an otherwise empty item.
        if (content[0]?.type !== 'paragraph') content.unshift({ type: 'paragraph' });
        return { type: block.type === 'taskList' ? 'taskItem' : 'listItem', ...(block.type === 'taskList' ? { attrs: { checked: item.checked } } : {}), content };
      }),
    };
  });
}

export function noteMarkdownToTipTap(value) {
  return blocksToTipTap(parseNoteMarkdown(value));
}

export function noteAITextForCodeBlock(value) {
  const text = String(value || '').replace(/\r\n?/g, '\n').trim();
  const fenced = /^(`{3,}|~{3,})[^\n]*\n([\s\S]*?)\n\1$/.exec(text);
  return fenced ? fenced[2] : text;
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
    if (segment.strike) value = `<s>${value}</s>`;
    if (segment.href) value = `<a href="${escapeHtml(segment.href)}" target="_blank" rel="noopener noreferrer">${value}</a>`;
    return value;
  }).join('');
}

export function noteMarkdownBlockToSafeHtml(block) {
  if (block.type === 'paragraph') return `<p>${inlineToHtml(block.segments)}</p>`;
  if (block.type === 'heading') return `<h${block.level}>${inlineToHtml(block.segments)}</h${block.level}>`;
  if (block.type === 'codeBlock') return `<pre><code>${escapeHtml(block.text)}</code></pre>`;
  if (block.type === 'horizontalRule') return '<hr>';
  if (block.type === 'blockquote' || block.type === 'callout') {
    const content = block.children.map(noteMarkdownBlockToSafeHtml).join('');
    return block.type === 'callout' ? `<aside data-callout="${escapeHtml(block.kind)}">${content}</aside>` : `<blockquote>${content}</blockquote>`;
  }
  if (block.type === 'table') {
    const header = block.header.map((segments) => `<th>${inlineToHtml(segments)}</th>`).join('');
    const rows = block.rows.map((row) => `<tr>${row.map((segments) => `<td>${inlineToHtml(segments)}</td>`).join('')}</tr>`).join('');
    return `<div class="table-wrap"><table><thead><tr>${header}</tr></thead><tbody>${rows}</tbody></table></div>`;
  }
  const tag = block.type === 'orderedList' ? 'ol' : 'ul';
  const start = tag === 'ol' && block.start !== 1 ? ` start="${block.start}"` : '';
  const tasks = block.type === 'taskList';
  const items = block.items.map((item) => {
    const check = tasks ? `<input type="checkbox" disabled${item.checked ? ' checked' : ''}>` : '';
    return `<li>${check}${item.children.map(noteMarkdownBlockToSafeHtml).join('')}</li>`;
  }).join('');
  return `<${tag}${start}${tasks ? ' data-type="taskList"' : ''}>${items}</${tag}>`;
}

export function noteMarkdownToSafeHtml(value) {
  return parseNoteMarkdown(value).map(noteMarkdownBlockToSafeHtml).join('');
}
