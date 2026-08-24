import { noteCalloutMeta } from './noteCallouts.js';
import { normalizeNoteHref } from './noteLinks.js';
import { noteMarkdownToSafeHtml } from './noteMarkdown.js';

function escapeMarkdown(value) {
  return String(value ?? '').replace(/([\\`*_[\]<>])/g, '\\$1');
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function paperMindTarget(type, id, page = null) {
  const targetType = encodeURIComponent(String(type || 'note'));
  const targetId = encodeURIComponent(String(id || ''));
  const pageSuffix = page ? `?page=${encodeURIComponent(String(page))}` : '';
  return `papermind://${targetType}/${targetId}${pageSuffix}`;
}

function addDocumentSource(context, source = {}) {
  const id = source.id || source.docId || source.documentId || null;
  const title = String(source.title || source.docTitle || source.label || 'Dokument').trim();
  const key = id ? `id:${id}` : `title:${title.toLocaleLowerCase('de')}`;
  const existing = context.sources.get(key) || { id, title, pages: new Set() };
  if (!existing.id && id) existing.id = id;
  if ((!existing.title || existing.title === 'Dokument') && title) existing.title = title;
  const page = Number(source.page);
  if (Number.isFinite(page) && page > 0) existing.pages.add(Math.round(page));
  context.sources.set(key, existing);
}

function renderText(node) {
  let value = String(node.text || '');
  const marks = Array.isArray(node.marks) ? node.marks : [];

  for (const mark of marks) {
    if (mark.type === 'code') {
      value = `\`${value.replace(/`/g, '\\`')}\``;
    } else if (mark.type === 'bold') {
      value = `**${value}**`;
    } else if (mark.type === 'italic') {
      value = `_${value}_`;
    } else if (mark.type === 'strike') {
      value = `~~${value}~~`;
    } else if (mark.type === 'underline') {
      value = `<u>${value}</u>`;
    } else if (mark.type === 'link' && mark.attrs?.href) {
      const href = normalizeNoteHref(mark.attrs.href);
      if (href) value = `[${value}](${href})`;
    }
  }
  return value;
}

function renderHtmlText(node) {
  let value = escapeHtml(node.text || '');
  const marks = Array.isArray(node.marks) ? node.marks : [];
  for (const mark of marks) {
    if (mark.type === 'code') value = `<code>${value}</code>`;
    else if (mark.type === 'bold') value = `<strong>${value}</strong>`;
    else if (mark.type === 'italic') value = `<em>${value}</em>`;
    else if (mark.type === 'strike') value = `<s>${value}</s>`;
    else if (mark.type === 'underline') value = `<u>${value}</u>`;
    else if (mark.type === 'link' && mark.attrs?.href) {
      const href = normalizeNoteHref(mark.attrs.href);
      if (href) {
        value = `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${value}</a>`;
      }
    }
  }
  return value;
}

function renderChildren(node, context, separator = '') {
  return (node.content || []).map((child) => renderNode(child, context)).filter(Boolean).join(separator);
}

function renderListItem(node, context, marker) {
  const rendered = renderChildren(node, context, '\n\n').trim();
  if (!rendered) return marker.trimEnd();
  return `${marker}${rendered.replace(/\n/g, '\n  ')}`;
}

function renderMarkdownTableCell(node, context) {
  if (!node) return ' ';
  return renderChildren(node, context, '<br>')
    .trim()
    .replace(/\r?\n/g, '<br>')
    .replace(/\|/g, '\\|') || ' ';
}

function renderMarkdownTable(node, context) {
  const rows = (node.content || []).filter((row) => row?.type === 'tableRow');
  if (!rows.length) return '';
  const columnCount = Math.max(...rows.map((row) => row.content?.length || 0), 1);
  const normalizeRow = (row) => Array.from(
    { length: columnCount },
    (_, index) => renderMarkdownTableCell(row?.content?.[index], context),
  );
  const firstRowIsHeader = (rows[0].content || []).some((cell) => cell?.type === 'tableHeader');
  const header = firstRowIsHeader ? normalizeRow(rows[0]) : Array(columnCount).fill(' ');
  const bodyRows = (firstRowIsHeader ? rows.slice(1) : rows).map(normalizeRow);
  return [
    `| ${header.join(' | ')} |`,
    `| ${Array(columnCount).fill('---').join(' | ')} |`,
    ...bodyRows.map((row) => `| ${row.join(' | ')} |`),
  ].join('\n');
}

function renderNode(node, context) {
  if (!node || typeof node !== 'object') return '';

  switch (node.type) {
    case 'doc':
      return renderChildren(node, context, '\n\n');
    case 'text':
      return renderText(node);
    case 'paragraph':
      return renderChildren(node, context);
    case 'heading': {
      const level = Math.min(6, Math.max(1, Number(node.attrs?.level) || 2));
      return `${'#'.repeat(level)} ${renderChildren(node, context)}`.trimEnd();
    }
    case 'hardBreak':
      return '  \n';
    case 'horizontalRule':
      return '---';
    case 'blockquote':
      return renderChildren(node, context, '\n\n')
        .split('\n')
        .map((line) => `> ${line}`.trimEnd())
        .join('\n');
    case 'bulletList':
      return (node.content || []).map((item) => renderListItem(item, context, '- ')).join('\n');
    case 'orderedList': {
      const start = Number(node.attrs?.start) || 1;
      return (node.content || [])
        .map((item, index) => renderListItem(item, context, `${start + index}. `))
        .join('\n');
    }
    case 'taskList':
      return (node.content || []).map((item) => {
        const marker = item.attrs?.checked ? '- [x] ' : '- [ ] ';
        return renderListItem(item, context, marker);
      }).join('\n');
    case 'listItem':
    case 'taskItem':
      return renderChildren(node, context, '\n\n');
    case 'codeBlock': {
      const language = node.attrs?.language || '';
      return `\`\`\`${language}\n${renderChildren(node, context)}\n\`\`\``;
    }
    case 'table':
      return renderMarkdownTable(node, context);
    case 'documentChip': {
      const attrs = node.attrs || {};
      addDocumentSource(context, attrs);
      return `[${escapeMarkdown(attrs.title || 'Dokument')}](${paperMindTarget('document', attrs.docId)})`;
    }
    case 'ocrQuote': {
      const attrs = node.attrs || {};
      addDocumentSource(context, attrs);
      const sourceLabel = `${attrs.docTitle || 'Dokument'}${attrs.page ? `, S. ${attrs.page}` : ''}`;
      const target = paperMindTarget('document', attrs.docId, attrs.page);
      const quote = String(attrs.text || '').split('\n').map((line) => `> ${line}`).join('\n');
      return `${quote}\n>\n> Quelle: [${escapeMarkdown(sourceLabel)}](${target})`;
    }
    case 'wikiLink': {
      const attrs = node.attrs || {};
      if (attrs.targetType === 'document') {
        addDocumentSource(context, { id: attrs.targetId, title: attrs.label });
      }
      return `[${escapeMarkdown(attrs.label || 'Verweis')}](${paperMindTarget(attrs.targetType, attrs.targetId)})`;
    }
    case 'aiBlock': {
      for (const source of node.attrs?.sources || []) addDocumentSource(context, source);
      const answer = String(node.attrs?.text || '').split('\n').map((line) => `> ${line}`).join('\n');
      return `> **PaperMind-KI**\n>\n${answer}`;
    }
    case 'callout': {
      const meta = noteCalloutMeta(node.attrs?.kind);
      const content = renderChildren(node, context, '\n\n')
        .split('\n')
        .map((line) => `> ${line}`.trimEnd())
        .join('\n');
      return `> **${meta.glyph} ${meta.label}**\n>\n${content}`;
    }
    default:
      return renderChildren(node, context);
  }
}

function renderHtmlChildren(node, context, separator = '') {
  return (node.content || []).map((child) => renderHtmlNode(child, context)).filter(Boolean).join(separator);
}

function renderHtmlTableCell(node, context) {
  const tag = node?.type === 'tableHeader' ? 'th' : 'td';
  const colspan = Math.max(1, Number(node?.attrs?.colspan) || 1);
  const rowspan = Math.max(1, Number(node?.attrs?.rowspan) || 1);
  const spanAttrs = `${colspan > 1 ? ` colspan="${colspan}"` : ''}${rowspan > 1 ? ` rowspan="${rowspan}"` : ''}`;
  return `<${tag}${spanAttrs}>${renderHtmlChildren(node, context) || '<p><br></p>'}</${tag}>`;
}

function renderHtmlTable(node, context) {
  const rows = (node.content || []).filter((row) => row?.type === 'tableRow');
  if (!rows.length) return '';
  const renderRow = (row) => `<tr>${(row.content || []).map((cell) => renderHtmlTableCell(cell, context)).join('')}</tr>`;
  const firstRowIsHeader = (rows[0].content || []).some((cell) => cell?.type === 'tableHeader');
  const head = firstRowIsHeader ? `<thead>${renderRow(rows[0])}</thead>` : '';
  const bodyRows = firstRowIsHeader ? rows.slice(1) : rows;
  const body = `<tbody>${bodyRows.map(renderRow).join('')}</tbody>`;
  return `<div class="table-wrap"><table>${head}${body}</table></div>`;
}

function renderHtmlNode(node, context) {
  if (!node || typeof node !== 'object') return '';

  switch (node.type) {
    case 'doc':
      return renderHtmlChildren(node, context);
    case 'text':
      return renderHtmlText(node);
    case 'paragraph':
      return `<p>${renderHtmlChildren(node, context) || '<br>'}</p>`;
    case 'heading': {
      const level = Math.min(6, Math.max(1, Number(node.attrs?.level) || 2));
      return `<h${level}>${renderHtmlChildren(node, context)}</h${level}>`;
    }
    case 'hardBreak':
      return '<br>';
    case 'horizontalRule':
      return '<hr>';
    case 'blockquote':
      return `<blockquote>${renderHtmlChildren(node, context)}</blockquote>`;
    case 'bulletList':
      return `<ul>${renderHtmlChildren(node, context)}</ul>`;
    case 'orderedList': {
      const start = Number(node.attrs?.start) || 1;
      return `<ol start="${start}">${renderHtmlChildren(node, context)}</ol>`;
    }
    case 'taskList':
      return `<ul class="task-list">${renderHtmlChildren(node, context)}</ul>`;
    case 'listItem':
      return `<li>${renderHtmlChildren(node, context)}</li>`;
    case 'taskItem': {
      const checked = node.attrs?.checked ? ' checked' : '';
      return `<li><input type="checkbox" disabled${checked}>${renderHtmlChildren(node, context)}</li>`;
    }
    case 'codeBlock':
      return `<pre><code>${escapeHtml((node.content || []).map((child) => child.text || '').join(''))}</code></pre>`;
    case 'table':
      return renderHtmlTable(node, context);
    case 'documentChip': {
      const attrs = node.attrs || {};
      addDocumentSource(context, attrs);
      return `<a class="pm-reference" href="${paperMindTarget('document', attrs.docId)}">${escapeHtml(attrs.title || 'Dokument')}</a>`;
    }
    case 'ocrQuote': {
      const attrs = node.attrs || {};
      addDocumentSource(context, attrs);
      const label = `${attrs.docTitle || 'Dokument'}${attrs.page ? ` · S. ${attrs.page}` : ''}`;
      return `<blockquote class="ocr-quote"><p>${escapeHtml(attrs.text || '')}</p><cite><a href="${paperMindTarget('document', attrs.docId, attrs.page)}">${escapeHtml(label)}</a></cite></blockquote>`;
    }
    case 'wikiLink': {
      const attrs = node.attrs || {};
      if (attrs.targetType === 'document') addDocumentSource(context, { id: attrs.targetId, title: attrs.label });
      return `<a class="pm-reference" href="${paperMindTarget(attrs.targetType, attrs.targetId)}">${escapeHtml(attrs.label || 'Verweis')}</a>`;
    }
    case 'aiBlock': {
      for (const source of node.attrs?.sources || []) addDocumentSource(context, source);
      return `<aside class="ai-block"><strong>PaperMind-KI</strong><div>${noteMarkdownToSafeHtml(node.attrs?.text || '')}</div></aside>`;
    }
    case 'callout': {
      const meta = noteCalloutMeta(node.attrs?.kind);
      return `<aside class="callout callout-${meta.value}"><strong>${escapeHtml(meta.glyph)} ${escapeHtml(meta.label)}</strong><div>${renderHtmlChildren(node, context)}</div></aside>`;
    }
    default:
      return renderHtmlChildren(node, context);
  }
}

function renderSources(context) {
  if (!context.sources.size) return '';
  const lines = [...context.sources.values()]
    .sort((left, right) => left.title.localeCompare(right.title, 'de', { sensitivity: 'base' }))
    .map((source) => {
      const label = escapeMarkdown(source.title || 'Dokument');
      const title = source.id ? `[${label}](${paperMindTarget('document', source.id)})` : label;
      const pages = [...source.pages].sort((left, right) => left - right);
      const pageLabel = pages.length ? ` — ${pages.length === 1 ? 'Seite' : 'Seiten'} ${pages.join(', ')}` : '';
      return `- ${title}${pageLabel}`;
    });
  return `## Quellen\n\n${lines.join('\n')}`;
}

export function noteToMarkdown({ title, body } = {}) {
  const context = { sources: new Map() };
  if (body?.attrs?.linkedDocument) addDocumentSource(context, body.attrs.linkedDocument);
  const content = renderNode(body, context).trim();
  const sources = renderSources(context);
  return [`# ${escapeMarkdown(String(title || '').trim() || 'Ohne Titel')}`, content, sources]
    .filter(Boolean)
    .join('\n\n')
    .concat('\n');
}

export function noteExportFilename(title) {
  const base = String(title || 'Notiz')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9ÄÖÜäöüß_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80);
  return `${base || 'Notiz'}.md`;
}

export function notePrintTitle(title) {
  return noteExportFilename(title).replace(/\.md$/, '');
}

export function noteToPrintableHtml({
  title,
  body,
  fontFamily = 'sans',
  paragraphSpacing = 'comfortable',
} = {}) {
  const context = { sources: new Map() };
  if (body?.attrs?.linkedDocument) addDocumentSource(context, body.attrs.linkedDocument);
  const content = renderHtmlNode(body, context);
  const sources = [...context.sources.values()]
    .sort((left, right) => left.title.localeCompare(right.title, 'de', { sensitivity: 'base' }))
    .map((source) => {
      const pages = [...source.pages].sort((left, right) => left - right);
      const pageLabel = pages.length ? ` — ${pages.length === 1 ? 'Seite' : 'Seiten'} ${pages.join(', ')}` : '';
      const label = `${escapeHtml(source.title || 'Dokument')}${escapeHtml(pageLabel)}`;
      return source.id
        ? `<li><a href="${paperMindTarget('document', source.id)}">${label}</a></li>`
        : `<li>${label}</li>`;
    })
    .join('');
  const fontStack = {
    serif: 'Georgia, "Times New Roman", serif',
    mono: 'ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, monospace',
    sans: '"Helvetica Neue", Helvetica, Arial, sans-serif',
  }[fontFamily] || '"Helvetica Neue", Helvetica, Arial, sans-serif';
  const paragraphGap = { compact: '0.45em', spacious: '1.05em', comfortable: '0.7em' }[paragraphSpacing] || '0.7em';
  const safeTitle = escapeHtml(String(title || '').trim() || 'Ohne Titel');

  return `<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>${safeTitle}</title>
  <style>
    @page { size: A4; margin: 20mm 22mm; }
    * { box-sizing: border-box; }
    body { margin: 0; color: #172126; font-family: ${fontStack}; font-size: 11pt; line-height: 1.62; }
    header { margin-bottom: 12mm; padding-bottom: 5mm; border-bottom: 1px solid #d8dfe1; }
    .eyebrow { color: #527078; font: 8pt ui-monospace, monospace; letter-spacing: .12em; text-transform: uppercase; }
    h1.title { margin: 2mm 0 0; font: 650 24pt/1.15 ${fontStack}; }
    main > * + * { margin-top: ${paragraphGap}; }
    h1, h2, h3, h4 { break-after: avoid; font-family: ${fontStack}; line-height: 1.25; }
    h1 { font-size: 19pt; } h2 { font-size: 15pt; } h3 { font-size: 12.5pt; } h4 { font-size: 11pt; }
    p { margin-bottom: 0; } ul, ol { padding-left: 1.5em; }
    blockquote { margin-left: 0; padding-left: 4mm; border-left: 2px solid #3e9ca4; color: #4f5f64; }
    .ocr-quote, .ai-block { padding: 4mm; border-radius: 2mm; background: #f1f5f6; break-inside: avoid; }
    .callout { margin: 4mm 0; padding: 3.5mm 4mm; border: 1px solid #d8dfe1; border-left: 3px solid #b7791f; border-radius: 2mm; background: #fff9ed; break-inside: avoid; }
    .callout > strong { display: block; margin-bottom: 1.5mm; color: #8a5a12; font-size: 9pt; letter-spacing: .05em; text-transform: uppercase; }
    .callout-question { border-left-color: #006b75; background: #eefafa; } .callout-question > strong { color: #006b75; }
    .callout-decision { border-left-color: #2f855a; background: #f0faf4; } .callout-decision > strong { color: #2f855a; }
    .callout-deadline { border-left-color: #c84c4c; background: #fff4f4; } .callout-deadline > strong { color: #a53b3b; }
    .callout-source { border-left-color: #5b6fb8; background: #f4f6ff; } .callout-source > strong { color: #485c9f; }
    .callout p:first-child, .callout p:last-child { margin-top: 0; margin-bottom: 0; }
    .ocr-quote cite { font-size: 8.5pt; font-style: normal; }
    pre { padding: 4mm; overflow-wrap: anywhere; border: 1px solid #d8dfe1; background: #f1f5f6; white-space: pre-wrap; }
    code { font-family: ui-monospace, monospace; }
    a { color: #006b75; text-decoration: none; }
    .pm-reference { padding: 0 1.5mm; border: 1px solid #b9dadd; border-radius: 1.5mm; }
    .task-list { list-style: none; padding-left: 0; }
    .table-wrap { max-width: 100%; overflow-x: auto; break-inside: avoid; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 9.5pt; }
    th, td { padding: 2.5mm 3mm; border: 1px solid #cbd4d7; vertical-align: top; overflow-wrap: anywhere; }
    th { background: #eaf4f4; color: #174f55; font-weight: 650; text-align: left; }
    th p, td p { margin: 0; }
    .sources { margin-top: 14mm; padding-top: 6mm; border-top: 1px solid #d8dfe1; break-before: auto; }
    .sources h2 { font-size: 14pt; }
    footer { position: fixed; right: 0; bottom: -12mm; color: #718086; font-size: 8pt; }
  </style>
</head>
<body>
  <header><div class="eyebrow">PaperMind · Notiz</div><h1 class="title">${safeTitle}</h1></header>
  <main>${content}</main>
  ${sources ? `<section class="sources"><h2>Quellen</h2><ul>${sources}</ul></section>` : ''}
  <footer>Exportiert aus PaperMind</footer>
</body>
</html>`;
}
