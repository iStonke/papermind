/*
 * Brücke zwischen der reinen Review-Logik (utils/noteReview.js) und dem
 * ProseMirror-Dokument. Hier – und nur hier – werden Zeichen-Offsets in echte
 * Editor-Positionen übersetzt und die bestätigten Änderungen in EINER
 * Transaktion (ein Undo-Schritt) angewandt.
 */
import { closeHistory } from '@tiptap/pm/history';
import { noteMarkdownToTipTap } from '../../../utils/noteMarkdown.js';

/**
 * Flacht das Dokument zu genau dem Text ab, der ans Modell geht, und merkt sich
 * für jedes Zeichen die ProseMirror-Position. Blöcke werden mit „\n" getrennt;
 * ein Trenner zeigt auf die Blockgrenze davor (nützlich für „insert_before").
 * @returns {{ text: string, map: number[] }}
 */
export function flattenReviewDoc(doc) {
  let text = '';
  const map = [];
  let firstBlock = true;
  doc.descendants((node, pos) => {
    if (node.isText) {
      const value = node.text || '';
      for (let k = 0; k < value.length; k += 1) map.push(pos + k);
      text += value;
      return false;
    }
    if (node.isTextblock) {
      if (!firstBlock) {
        text += '\n';
        map.push(pos); // Trenner ↦ Grenze unmittelbar vor diesem Block
      }
      firstBlock = false;
      return true;
    }
    return true;
  });
  return { text, map };
}

/** Stable per-request block references; metadata excludes private node attributes. */
export function reviewDocumentBlocks(doc) {
  const blocks = [];
  doc.forEach((node, pos, index) => {
    const structure = [];
    let protectedContent = false;
    const describe = (child) => {
      if (structure.length < 80) structure.push({
        type: child.type.name,
        ...(child.type.name === 'heading' ? { level: child.attrs.level } : {}),
        ...(child.type.name === 'callout' ? { kind: child.attrs.kind } : {}),
        ...(child.marks.length ? { marks: child.marks.map(mark => mark.type.name) } : {}),
      });
      if (!['paragraph', 'heading', 'text', 'hardBreak', 'bulletList', 'orderedList', 'listItem', 'taskList', 'taskItem', 'callout', 'blockquote', 'table', 'tableRow', 'tableHeader', 'tableCell'].includes(child.type.name)) protectedContent = true;
      if (child.type.name === 'taskItem' && (child.attrs.checked || child.attrs.dueDate)) protectedContent = true;
      if (child.marks.some(mark => !['bold', 'italic', 'strike', 'code'].includes(mark.type.name))) protectedContent = true;
      if (child.attrs.colspan > 1 || child.attrs.rowspan > 1 || child.attrs.colwidth) protectedContent = true;
    };
    describe(node);
    node.descendants(describe);
    blocks.push({ id: `b${index + 1}`, type: node.type.name, text: flattenReviewDoc(node).text,
      structure, convertible: !protectedContent, from: pos, to: pos + node.nodeSize, json: node.toJSON() });
  });
  return blocks;
}

export function reviewStructureContext(doc) {
  return reviewDocumentBlocks(doc).slice(0, 1000).map(({ id, type, text, structure, convertible }) => ({ id, type, text, structure, convertible }));
}

function resolveBlockTarget(doc, change) {
  const blocks = reviewDocumentBlocks(doc);
  let selected;
  if (change.blockSnapshot) {
    // Earlier accepted edits can shift block numbers. Reuse only the exact,
    // unchanged source blocks, and reject ambiguous duplicate matches.
    const originals = JSON.parse(change.blockSnapshot);
    const matches = blocks.map((_, i) => blocks.slice(i, i + originals.length))
      .filter(items => JSON.stringify(items.map(item => item.json)) === change.blockSnapshot);
    if (matches.length !== 1) return null;
    selected = matches[0];
  } else {
    selected = change.blockIds.map(id => blocks.find(block => block.id === id));
  }
  if (!selected.length || selected.some(block => !block || !block.convertible)) return null;
  if (selected.some((block, i) => i > 0 && selected[i - 1].to !== block.from)) return null;
  if (selected.map(block => block.text).join('\n') !== change.anchor) return null;
  return {
    from: selected[0].from + 1, to: selected.at(-1).to - 1,
    blockFrom: selected[0].from, blockTo: selected.at(-1).to,
    blockSnapshot: JSON.stringify(selected.map(block => block.json)),
  };
}

/** Übersetzt einen Zeichenbereich [charFrom, charTo) in ein PM-Bereichspaar. */
function charRangeToPos(map, docSize, charFrom, charTo) {
  const from = map[charFrom];
  const lastChar = Math.max(charFrom, charTo - 1);
  const to = Math.min((map[lastChar] ?? map[charFrom]) + 1, docSize);
  return { from, to };
}

/** Findet den umschließenden Textblock einer Position (Bereich + Momentaufnahme). */
function containingBlock(doc, pos) {
  const $pos = doc.resolve(Math.min(pos, doc.content.size));
  for (let depth = $pos.depth; depth >= 0; depth -= 1) {
    const node = $pos.node(depth);
    if (node.isTextblock) {
      return {
        blockFrom: $pos.before(depth),
        blockTo: $pos.after(depth),
        snapshot: JSON.stringify(node.toJSON()),
      };
    }
  }
  return { blockFrom: pos, blockTo: pos, snapshot: '' };
}

/**
 * Reichert die (bereits aufgelösten) Änderungen mit echten Editor-Positionen an.
 * Nicht auffindbare Änderungen bleiben `found: false` und ohne Positionen.
 */
export function resolveReviewPositions(doc, map, changes) {
  const docSize = doc.content.size;
  return changes.map((change) => {
    if (change.blockIds?.length) {
      const target = resolveBlockTarget(doc, change);
      return target ? { ...change, ...target, found: true } : { ...change, found: false };
    }
    if (!change.found || !Number.isInteger(map[change.charFrom])) {
      return { ...change, found: false };
    }
    const { from, to } = charRangeToPos(map, docSize, change.charFrom, change.charTo);
    const block = containingBlock(doc, from);
    return { ...change, found: true, from, to, ...block };
  });
}

/**
 * Baut den konkreten Editor-Eingriff für eine Änderung. Inline-Korrekturen
 * ersetzen nur die Textstelle; Formatierungen/Ergänzungen, die zu Blöcken
 * werden, ersetzen bzw. ergänzen ganze Blöcke.
 */
export function buildReviewEdit(change) {
  const nodes = noteMarkdownToTipTap(change.revised || '');
  if (!nodes.length) return null;

  if (change.blockIds?.length) {
    if (change.cat !== 'format' || !change.blockSnapshot) return null;
    return { id: change.id, kind: 'block', from: change.blockFrom, to: change.blockTo, content: nodes };
  }

  const singleParagraph = nodes.length === 1 && nodes[0].type === 'paragraph';
  const inline = singleParagraph ? (nodes[0].content || []) : null;

  if (change.cat === 'add') {
    // Ergänzungen fügen NEUEN Inhalt ein und überschreiben die Bezugsstelle nie.
    const pos = change.insertBefore ? change.blockFrom : change.blockTo;
    return { id: change.id, kind: 'insert', from: pos, to: pos, content: nodes };
  }

  // fix/format: bleibt es ein einzelner Absatz, genügt eine Inline-Ersetzung.
  if (singleParagraph) {
    if (!inline.length) return null;
    return { id: change.id, kind: 'inline', from: change.from, to: change.to, content: inline };
  }
  // Never replace a whole block when only part of its text was anchored.
  if (change.from !== change.blockFrom + 1 || change.to !== change.blockTo - 1) return null;
  return { id: change.id, kind: 'block', from: change.blockFrom, to: change.blockTo, content: nodes };
}

function rangesOverlap(a, b) {
  return a.from < b.to && b.from < a.to;
}

/**
 * Wählt aus den bestätigten Änderungen die tatsächlich anwendbaren aus und
 * löst Überlappungen ersetzender Eingriffe auf (der größere Bereich gewinnt,
 * weil eine Blockformatierung eine darin liegende Einzelkorrektur bereits
 * enthält). Ergänzungen sind punktförmig und kollidieren nie.
 * @returns {{ edits: object[], skipped: number[] }}
 */
export function planReviewEdits(changes) {
  const edits = [];
  const skipped = [];
  for (const change of changes) {
    const edit = buildReviewEdit(change);
    if (!edit) { skipped.push(change.id); continue; }
    edits.push(edit);
  }

  const replaces = edits
    .filter((edit) => edit.kind !== 'insert')
    .sort((a, b) => (b.to - b.from) - (a.to - a.from)); // größter Bereich zuerst
  const accepted = [];
  for (const edit of replaces) {
    if (accepted.some((kept) => rangesOverlap(kept, edit))) {
      skipped.push(edit.id);
      continue;
    }
    accepted.push(edit);
  }
  const inserts = edits.filter((edit) => edit.kind === 'insert');
  return { edits: [...accepted, ...inserts], skipped };
}

/** Prüft, ob sich die Zielblöcke seit dem Auflösen nicht verändert haben. */
export function reviewChangesStillValid(doc, changes) {
  return changes.every((change) => {
    if (change.blockSnapshot) {
      if (change.blockFrom < 0 || change.blockTo > doc.content.size) return false;
      return JSON.stringify(doc.slice(change.blockFrom, change.blockTo).content.toJSON()) === change.blockSnapshot;
    }
    if (!change.found || !change.snapshot) return true;
    const node = doc.nodeAt(change.blockFrom);
    return node ? JSON.stringify(node.toJSON()) === change.snapshot : false;
  });
}

/**
 * Wendet die geplanten Eingriffe in EINER Transaktion an. `closeHistory` sorgt
 * dafür, dass die ganze Übernahme mit einem einzigen Undo rückgängig wird.
 * Eingriffe werden von hinten nach vorn eingespielt, damit frühere Positionen
 * gültig bleiben.
 * @returns {number} Anzahl angewandter Eingriffe
 */
export function applyReviewEdits(editor, edits) {
  if (!editor || !edits.length) return 0;
  const ordered = [...edits].sort((a, b) => b.from - a.from);
  const chain = editor.chain().focus().command(({ tr }) => { closeHistory(tr); return true; });
  for (const edit of ordered) {
    chain.insertContentAt({ from: edit.from, to: edit.to }, edit.content);
  }
  chain.scrollIntoView().run();
  return ordered.length;
}
