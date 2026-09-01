/*
 * templateBox / templateField — gefärbter Vorlagen-Block mit beschrifteten
 * Feldzeilen. Der Block hebt sich optisch wie ein Callout ab und unterstützt vor
 * allem Vorlagen ("Gesprächsnotiz" & Co.):
 *
 *  - templateBox  : Kopfzeile mit editierbarem Titel + Farbvariante, Inhalt = 1..n
 *                   templateField.
 *  - templateField: eine Zeile aus Label (Attribut, umbenennbar) + editierbarem
 *                   Wert. Ist der Wert leer, zeigt die NodeView den `hint` als
 *                   Platzhalter an — er ist reines Chrome und wird NICHT
 *                   gespeichert, lässt sich also einfach übertippen.
 *
 * Tastatur (in einem Feld):
 *  - Enter / Tab      : nächstes Feld; am Ende neue Zeile bzw. Block verlassen.
 *  - Shift-Tab        : vorheriges Feld.
 *  - Backspace (leer) : leere Zeile löschen und zum vorherigen Feld springen.
 */
import { Node, mergeAttributes, VueNodeViewRenderer } from '@tiptap/vue-3';
import TemplateBoxView from './TemplateBoxView.vue';
import TemplateFieldView from './TemplateFieldView.vue';
import { normalizeTemplateVariant, normalizeTemplateColor, newTemplateFieldAttrs } from './noteTemplates.js';

/* ── Positions-Helfer für die Feld-Navigation ──────────────────────────────── */
function fieldContext(state) {
  const { $from } = state.selection;
  for (let depth = $from.depth; depth > 0; depth -= 1) {
    if ($from.node(depth).type.name !== 'templateField') continue;
    const box = $from.node(depth - 1);
    if (box?.type.name !== 'templateBox') continue;
    return {
      field: $from.node(depth),
      box,
      index: $from.index(depth - 1),
      boxBefore: $from.before(depth - 1),
      fieldBefore: $from.before(depth),
      fieldAfter: $from.after(depth),
      boxAfter: $from.after(depth - 1),
    };
  }
  return null;
}

// Absolute Position DIREKT im Feld `index` des Blocks (Offset 0).
function fieldInnerStart(ctx, index) {
  let pos = ctx.boxBefore + 1;
  for (let i = 0; i < index; i += 1) pos += ctx.box.child(i).nodeSize;
  return pos + 1;
}

function moveToField(editor, ctx, index, atEnd) {
  const field = ctx.box.child(index);
  const start = fieldInnerStart(ctx, index);
  const pos = atEnd ? start + field.content.size : start;
  return editor.chain().focus().setTextSelection(pos).run();
}

function addFieldAfter(editor, ctx) {
  const at = ctx.fieldAfter;
  return editor
    .chain()
    .insertContentAt(at, { type: 'templateField', attrs: newTemplateFieldAttrs() })
    .setTextSelection(at + 1)
    .focus()
    .run();
}

function exitBox(editor, ctx) {
  // Eine leere, unbenannte Gerüstzeile (per Enter angelegt, dann wieder Enter)
  // beim Verlassen entfernen. Ein leeres, BENANNTES Feld (z. B. "Ergebnis")
  // bleibt erhalten — dort ist die Lücke gewollt.
  const dropEmptyRow = ctx.box.childCount > 1 && !(ctx.field.attrs.label || '').trim();
  const at = dropEmptyRow ? ctx.boxAfter - (ctx.fieldAfter - ctx.fieldBefore) : ctx.boxAfter;
  const chain = editor.chain();
  if (dropEmptyRow) chain.deleteRange({ from: ctx.fieldBefore, to: ctx.fieldAfter });
  return chain
    .insertContentAt(at, { type: 'paragraph' })
    .setTextSelection(at + 1)
    .focus()
    .run();
}

/* ── Der Block ─────────────────────────────────────────────────────────────── */
export const TemplateBox = Node.create({
  name: 'templateBox',
  group: 'block',
  content: 'templateField+',
  defining: true,
  selectable: true,
  draggable: false,

  addOptions() {
    return {
      // Optionaler Callback (Workspace): ({ title, color, fields }) => void.
      // Ist er gesetzt, zeigt die Box „Als Baustein speichern".
      onSaveAsTemplate: null,
    };
  },

  addAttributes() {
    return {
      variant: {
        default: 'note',
        parseHTML: (element) => normalizeTemplateVariant(element.getAttribute('data-variant')),
        renderHTML: (attributes) => ({ 'data-variant': normalizeTemplateVariant(attributes.variant) }),
      },
      title: {
        default: '',
        parseHTML: (element) => element.getAttribute('data-title') || '',
        renderHTML: (attributes) => (attributes.title ? { 'data-title': attributes.title } : {}),
      },
      color: {
        default: 'teal',
        parseHTML: (element) => normalizeTemplateColor(element.getAttribute('data-color')),
        renderHTML: (attributes) => ({ 'data-color': normalizeTemplateColor(attributes.color) }),
      },
      insertedAt: {
        default: null,
        rendered: false,
      },
    };
  },

  parseHTML() {
    return [{ tag: 'section[data-template-box]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['section', mergeAttributes({ 'data-template-box': '' }, HTMLAttributes), 0];
  },

  addNodeView() {
    return VueNodeViewRenderer(TemplateBoxView);
  },

  addCommands() {
    return {
      insertTemplateBox: (preset = {}) => ({ commands }) => commands.insertContent({
        type: this.name,
        attrs: {
          variant: normalizeTemplateVariant(preset.variant),
          color: normalizeTemplateColor(preset.color),
          title: preset.title || '',
          insertedAt: new Date().toISOString(),
        },
        content: (Array.isArray(preset.fields) && preset.fields.length ? preset.fields : [{ label: '', hint: '' }])
          .map((field) => ({
            type: 'templateField',
            attrs: { label: field.label || '', hint: field.hint || '' },
          })),
      }),
      setTemplateBoxVariant: (variant) => ({ commands }) => commands.updateAttributes(
        this.name,
        { variant: normalizeTemplateVariant(variant) },
      ),
      setTemplateBoxColor: (color) => ({ commands }) => commands.updateAttributes(
        this.name,
        { color: normalizeTemplateColor(color) },
      ),
    };
  },
});

/* ── Die Feldzeile ─────────────────────────────────────────────────────────── */
export const TemplateField = Node.create({
  name: 'templateField',
  // Höhere Priorität, damit die Feld-Navigation (Enter/Tab/Backspace) VOR den
  // eingebauten Bindungen (splitBlock, joinBackward) greift.
  priority: 1000,
  content: 'inline*',
  defining: true,

  addAttributes() {
    return {
      label: {
        default: '',
        parseHTML: (element) => element.getAttribute('data-label') || '',
        renderHTML: (attributes) => ({ 'data-label': attributes.label || '' }),
      },
      hint: {
        default: '',
        parseHTML: (element) => element.getAttribute('data-hint') || '',
        renderHTML: (attributes) => (attributes.hint ? { 'data-hint': attributes.hint } : {}),
      },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-template-field]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes({ 'data-template-field': '' }, HTMLAttributes), 0];
  },

  addNodeView() {
    return VueNodeViewRenderer(TemplateFieldView);
  },

  addKeyboardShortcuts() {
    const lastIndex = (ctx) => ctx.box.childCount - 1;

    return {
      Enter: ({ editor }) => {
        const ctx = fieldContext(editor.state);
        if (!ctx) return false;
        if (ctx.index < lastIndex(ctx)) return moveToField(editor, ctx, ctx.index + 1, false);
        if (ctx.field.content.size === 0) return exitBox(editor, ctx);
        return addFieldAfter(editor, ctx);
      },
      Tab: ({ editor }) => {
        const ctx = fieldContext(editor.state);
        if (!ctx) return false;
        if (ctx.index < lastIndex(ctx)) return moveToField(editor, ctx, ctx.index + 1, true);
        return addFieldAfter(editor, ctx);
      },
      'Shift-Tab': ({ editor }) => {
        const ctx = fieldContext(editor.state);
        if (!ctx || ctx.index === 0) return false;
        return moveToField(editor, ctx, ctx.index - 1, true);
      },
      Backspace: ({ editor }) => {
        const ctx = fieldContext(editor.state);
        if (!ctx) return false;
        const { $from, empty } = editor.state.selection;
        if (!empty || $from.parentOffset !== 0) return false;
        if (ctx.field.content.size !== 0 || ctx.index === 0) return false;
        const prevInnerStart = fieldInnerStart(ctx, ctx.index - 1);
        const prevEnd = prevInnerStart + ctx.box.child(ctx.index - 1).content.size;
        return editor
          .chain()
          .deleteRange({ from: ctx.fieldBefore, to: ctx.fieldAfter })
          .setTextSelection(prevEnd)
          .focus()
          .run();
      },
    };
  },
});

export default TemplateBox;
