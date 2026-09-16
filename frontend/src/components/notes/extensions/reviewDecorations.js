import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

/*
 * Dekorationen für die KI-Überarbeitung (Variante 2B): je betroffener Textstelle
 * eine dezente Unterstreichung (farbig nach Kategorie) und unmittelbar dahinter
 * eine hochgestellte Ziffer, die der Nummer im Panel-Badge entspricht. Bei Fokus
 * bekommt der Anker zusätzlich einen Softton. Es wird NICHTS am Dokument
 * geändert; die Dekorationen sind rein visuell und werden vom Controller über
 * `setReviewDecorations` gespeist.
 */
const reviewDecorationsKey = new PluginKey('paperMindReviewDecorations');

function clamp(value, doc) {
  return Math.max(0, Math.min(Number(value) || 0, doc.content.size));
}

function numberWidget(spec) {
  const el = document.createElement('sup');
  el.className = spec.numberClass;
  el.textContent = String(spec.number);
  el.setAttribute('data-review-id', String(spec.id));
  el.setAttribute('aria-hidden', 'true');
  el.contentEditable = 'false';
  return el;
}

function buildDecorations(doc, specs) {
  const decorations = [];
  const focus = (specs || []).find((spec) => spec.focused && spec.to > spec.from);
  if (focus) {
    const from = clamp(focus.from, doc);
    const to = clamp(focus.to, doc);
    // Ganze fremde Teilbäume genau einmal dämpfen. Im Fokus-Teilbaum nur die
    // Textstücke außerhalb des Ankers: Eltern dürfen den Fokus nicht mit dimmen.
    doc.descendants((node, pos) => {
      const end = pos + node.nodeSize;
      if (end <= from || pos >= to) {
        const attrs = { class: 'pm-review-muted' };
        decorations.push(node.isInline
          ? Decoration.inline(pos, end, attrs)
          : Decoration.node(pos, end, attrs));
        return false;
      }
      if (node.isText) {
        if (pos < from) decorations.push(Decoration.inline(pos, from, { class: 'pm-review-muted' }));
        if (end > to) decorations.push(Decoration.inline(to, end, { class: 'pm-review-muted' }));
      }
      return true;
    });
  }
  for (const spec of specs || []) {
    const from = clamp(spec.from, doc);
    const to = clamp(spec.to, doc);
    if (to <= from) continue;
    decorations.push(Decoration.inline(from, to, {
      class: spec.class,
      'data-review-id': String(spec.id),
    }));
    if (spec.number != null) {
      decorations.push(Decoration.widget(to, () => numberWidget(spec), {
        side: 1,
        key: `rev-num-${spec.id}-${spec.number}-${spec.numberClass}`,
        ignoreSelection: true,
      }));
    }
  }
  return DecorationSet.create(doc, decorations);
}

export const NoteReviewDecorations = Extension.create({
  name: 'paperMindReviewDecorations',

  addProseMirrorPlugins() {
    return [new Plugin({
      key: reviewDecorationsKey,
      state: {
        init: () => DecorationSet.empty,
        apply(transaction, decorations) {
          const update = transaction.getMeta(reviewDecorationsKey);
          if (update?.hide) return DecorationSet.empty;
          if (Array.isArray(update?.specs)) return buildDecorations(transaction.doc, update.specs);
          return decorations.map(transaction.mapping, transaction.doc);
        },
      },
      props: {
        decorations(state) {
          return reviewDecorationsKey.getState(state) || DecorationSet.empty;
        },
      },
    })];
  },
});

export function setReviewDecorations(editor, specs) {
  if (!editor || editor.isDestroyed) return;
  editor.view.dispatch(
    editor.state.tr
      .setMeta(reviewDecorationsKey, { specs })
      .setMeta('addToHistory', false),
  );
}

export function clearReviewDecorations(editor) {
  if (!editor || editor.isDestroyed) return;
  editor.view.dispatch(
    editor.state.tr
      .setMeta(reviewDecorationsKey, { hide: true })
      .setMeta('addToHistory', false),
  );
}

export default NoteReviewDecorations;
