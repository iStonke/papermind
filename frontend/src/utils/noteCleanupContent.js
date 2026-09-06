import { noteMarkdownToTipTap } from './noteMarkdown.js';
import { noteContentToMarkdown } from './noteExport.js';
import { diffCleanupText } from './noteCleanup.js';

const CLEANUP_BLOCKS = new Set(['paragraph', 'heading', 'bulletList', 'orderedList', 'taskList', 'listItem', 'taskItem', 'text']);
const MARKDOWN_MARKS = new Set(['bold', 'italic', 'strike', 'code', 'link']);

export function cleanupSource(content) {
  return noteContentToMarkdown({ type: 'paragraph', content: content.map((node) => ({
    ...node, marks: node.marks?.filter((mark) => MARKDOWN_MARKS.has(mark.type)),
  })) });
}

// Preserve editor-only marks (e.g. highlight) on unchanged words. If the whole
// selection carries one such mark, keep it on the rewritten text as well.
function preserveEditorMarks(original, content) {
  let oldOffset = 0;
  const originalText = original.filter((node) => node.type === 'text').map((node) => {
    const span = { from: oldOffset, to: oldOffset + node.text.length, text: node.text, marks: (node.marks || []).filter((mark) => !MARKDOWN_MARKS.has(mark.type)) };
    oldOffset = span.to;
    return span;
  });
  if (!originalText.some((span) => span.marks.length)) return content;
  const common = (originalText[0]?.marks || []).filter((mark) => originalText.every((span) => span.marks.some((candidate) => JSON.stringify(candidate) === JSON.stringify(mark))));
  const texts = [];
  function collect(nodes) { nodes.forEach((node) => { if (node.type === 'text') texts.push(node.text); else if (node.content) collect(node.content); }); }
  collect(content);
  const mappings = [];
  let before = 0, after = 0;
  for (const part of diffCleanupText(originalText.map((span) => span.text).join(''), texts.join(''))) {
    if (part.type === 'equal') mappings.push({ from: after, to: after + part.text.length, oldFrom: before });
    if (part.type !== 'added') before += part.text.length;
    if (part.type !== 'removed') after += part.text.length;
  }
  let offset = 0;
  function restore(nodes) {
    return nodes.flatMap((node) => {
      if (node.type !== 'text') return [{ ...node, ...(node.content ? { content: restore(node.content) } : {}) }];
      const from = offset, to = from + node.text.length;
      offset = to;
      const pieces = [];
      for (let position = from; position < to; position += 1) {
        const mapping = mappings.find((range) => range.from <= position && position < range.to);
        const oldPosition = mapping ? mapping.oldFrom + position - mapping.from : -1;
        const marks = mapping ? (originalText.find((span) => span.from <= oldPosition && oldPosition < span.to)?.marks || []) : common;
        const combined = [...(node.marks || []), ...marks];
        const text = node.text[position - from];
        const previous = pieces.at(-1);
        if (previous && JSON.stringify(previous.marks || []) === JSON.stringify(combined)) previous.text += text;
        else pieces.push({ ...node, text, ...(combined.length ? { marks: combined } : {}) });
      }
      return pieces;
    });
  }
  return restore(content);
}

/** Build the exact replacement before committing any document transaction. */
export function cleanupReplacement(target, markdown) {
  const content = preserveEditorMarks(target.originalContent, noteMarkdownToTipTap(markdown));
  if (!content.length) throw new Error('Der Vorschlag enthält keinen Text.');
  function validate(nodes) {
    for (const node of nodes) {
      if (!CLEANUP_BLOCKS.has(node.type)) {
        throw new Error('Bitte den Vorschlag auf Absätze, kurze Listen und sparsame Hervorhebungen beschränken.');
      }
      if (node.content) validate(node.content);
    }
  }
  validate(content);
  // Returning an unchanged block must not discard existing marks or metadata.
  if (markdown.trim() === target.source) {
    return { from: target.from, to: target.to, content: target.originalContent };
  }
  const paragraph = content.length === 1 && content[0].type === 'paragraph';
  if (paragraph) {
    const inline = content[0].content || [];
    if (!inline.length) throw new Error('Der Vorschlag enthält keinen Text.');
    return { from: target.from, to: target.to, content: inline };
  }
  if (!target.allowBlocks) {
    throw new Error('In diesem Textbereich bitte nur den Text und Hervorhebungen ändern. Für eine neue Liste den vollständigen Absatz markieren.');
  }
  return { from: target.blockFrom, to: target.blockTo, content };
}
