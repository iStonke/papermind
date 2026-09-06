import { createRenderer } from 'vue';
import { Fragment, Schema, Slice } from '@tiptap/pm/model';
import { EditorState, TextSelection } from '@tiptap/pm/state';
import { history, undo } from '@tiptap/pm/history';

// Mount composable lifecycles without a browser or network connection.
export function mountController(factory) {
  const renderer = createRenderer({
    createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
    insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
    parentNode: () => null, nextSibling: () => null,
  });
  let controller;
  const app = renderer.createApp({ setup() { controller = factory(); return () => null; } });
  app.mount({});
  return { controller, unmount: () => app.unmount() };
}

const schema = new Schema({ nodes: {
  doc: { content: 'block+' },
  paragraph: { content: 'text*', group: 'block', attrs: { aiGeneration: { default: null } } },
  heading: { content: 'text*', group: 'block', attrs: { level: { default: 2 }, aiGeneration: { default: null } } },
  taskList: { content: 'taskItem+', group: 'block', attrs: { aiGeneration: { default: null } } },
  taskItem: { content: 'paragraph block*', attrs: { checked: { default: false } } },
  bulletList: { content: 'listItem+', group: 'block', attrs: { aiGeneration: { default: null } } },
  orderedList: { content: 'listItem+', group: 'block', attrs: { start: { default: 1 }, aiGeneration: { default: null } } },
  listItem: { content: 'paragraph block*' },
  text: { group: 'inline' },
  aiBlock: { group: 'block', atom: true, attrs: {
    text: { default: '' }, prompt: { default: '' }, provider: { default: '' },
    model: { default: '' }, generatedAt: { default: '' },
  } },
}, marks: {
  bold: {}, italic: {}, code: {}, strike: {}, highlight: { attrs: { color: { default: 'yellow' } } },
  link: { attrs: { href: {}, target: { default: null }, rel: { default: null } } },
} });

// Real ProseMirror documents, transactions, selections, and undo history.
// Only the DOM-dependent TipTap command facade is replaced.
export function createTestEditor(text = 'Original text', body = null) {
  const editor = {
    isDestroyed: false,
    state: EditorState.create({ schema, doc: body ? schema.nodeFromJSON(body) : schema.node('doc', null, [schema.node('paragraph', null, text ? schema.text(text) : [])]), plugins: [history()] }),
    getText() { return this.state.doc.textContent; },
    isActive() { return false; },
    getAttributes() { return {}; },
    view: { hasFocus: () => true, dispatch: (tr) => { editor.state = editor.state.apply(tr); } },
    commands: {
      setTextSelection(selection) { editor.view.dispatch(editor.state.tr.setSelection(TextSelection.create(editor.state.doc, selection.from ?? selection, selection.to ?? selection))); },
      undo() { return undo(editor.state, editor.view.dispatch); },
    },
    chain() {
      let tr = editor.state.tr;
      const chain = {
        focus() { return chain; }, scrollIntoView() { return chain; },
        command(callback) { callback({ tr, state: editor.state }); return chain; },
        setTextSelection(selection) { tr = tr.setSelection(TextSelection.create(tr.doc, selection.from ?? selection, selection.to ?? selection)); return chain; },
        setLink(attrs) { tr = tr.addMark(tr.selection.from, tr.selection.to, schema.marks.link.create(attrs)); return chain; },
        unsetLink() { tr = tr.removeMark(tr.selection.from, tr.selection.to, schema.marks.link); return chain; },
        insertAiBlock(attrs) { tr = tr.replaceRangeWith(tr.selection.from, tr.selection.to, schema.node('aiBlock', attrs)); return chain; },
        insertContentAt(range, json) {
          const content = (Array.isArray(json) ? json : [json]).map((node) => schema.nodeFromJSON(node));
          tr = tr.replaceRange(range.from ?? range, range.to ?? range, new Slice(Fragment.fromArray(content), 0, 0));
          return chain;
        },
        run() { editor.view.dispatch(tr); return true; },
      };
      return chain;
    },
  };
  return editor;
}
