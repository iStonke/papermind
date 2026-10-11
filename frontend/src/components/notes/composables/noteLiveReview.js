import { flattenReviewDoc, reviewDocumentBlocks } from './noteReviewDoc.js';
import { noteMarkdownToTipTap } from '../../../utils/noteMarkdown.js';

export const LIVE_REVIEW_DELAY = 3000;
export const LIVE_REVIEW_INTERVAL = 15000;
const CHUNK_LIMIT = 2000;

// Formatting may change markup, case and punctuation, but must not duplicate
// neighboring sentences or introduce words under a misleading category.
export function liveFormatPreservesText(change) {
  if (change.cat !== 'format') return true;
  const plainText = node => node.type === 'text' ? node.text || ''
    : (node.content || []).map(plainText).join(['paragraph', 'heading'].includes(node.type) ? '' : '\n');
  const revised = noteMarkdownToTipTap(change.revised).map(plainText).join('\n');
  const words = text => text.normalize('NFC').toLocaleLowerCase('de-DE').match(/[\p{L}\p{N}]+/gu) || [];
  const originalWords = words(change.anchor);
  const revisedWords = words(revised);
  return originalWords.length === revisedWords.length
    && originalWords.every((word, index) => word === revisedWords[index]);
}

// ProseMirror shares unchanged nodes between transactions. Remembering checked
// node identities avoids sending the entire note again after each keystroke.
// Long individual blocks are checked in bounded excerpts as well.
export function liveReviewScope(doc, checkedThrough) {
  const flat = flattenReviewDoc(doc);
  const blocks = reviewDocumentBlocks(doc).map((block, index) => ({
    ...block, node: doc.child(index),
  }));
  const index = blocks.findIndex(block => block.text.slice(checkedThrough.get(block.node) || 0).trim());
  if (index < 0) return null;
  const target = blocks[index];
  const checkedOffset = checkedThrough.get(target.node) || 0;
  const offset = checkedOffset + target.text.slice(checkedOffset).search(/\S/);
  const startOf = block => flat.map.findIndex(pos => pos > block.from && pos < block.to);
  let start = startOf(target) + offset;
  let end = Math.min(startOf(target) + target.text.length, start + CHUNK_LIMIT);
  if (end < startOf(target) + target.text.length) {
    const boundary = flat.text.lastIndexOf(' ', end);
    if (boundary > start + CHUNK_LIMIT / 2) end = boundary + 1;
  }
  const selected = [{ block: target, through: end - startOf(target) }];
  // Include nearby, complete blocks for context when the excerpt has room.
  if (!offset && index > 0) {
    const previous = blocks[index - 1];
    const previousStart = startOf(previous);
    if (previous.text && end - previousStart <= CHUNK_LIMIT) {
      start = previousStart;
      selected.unshift({ block: previous, through: previous.text.length });
    }
  }
  if (selected.at(-1).through === target.text.length) {
    for (const block of blocks.slice(index + 1)) {
      if (!block.text) continue;
      const nextEnd = startOf(block) + block.text.length;
      if (nextEnd - start > CHUNK_LIMIT) break;
      end = nextEnd;
      selected.push({ block, through: block.text.length });
    }
  }
  const complete = selected.filter(({ block, through }) => through === block.text.length
    && start <= startOf(block));
  return {
    text: flat.text.slice(start, end), map: flat.map.slice(start, end),
    from: flat.map[start], to: flat.map[end - 1] + 1,
    structure: complete.slice(0, 1000).map(({ block: { id, type, text, structure, convertible } }) => ({ id, type, text, structure, convertible })),
    checked: selected.map(({ block, through }) => [block.node, through]),
  };
}
