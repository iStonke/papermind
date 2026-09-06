import { createRenderer } from 'vue';
import { Schema } from '@tiptap/pm/model';
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
  paragraph: { content: 'text*', group: 'block' },
  text: { group: 'inline' },
  aiBlock: { group: 'block', atom: true, attrs: {
    text: { default: '' }, prompt: { default: '' }, provider: { default: '' },
    model: { default: '' }, generatedAt: { default: '' },
  } },
}, marks: {
  link: { attrs: { href: {}, target: { default: null }, rel: { default: null } } },
} });

// Real ProseMirror documents, transactions, selections, and undo history.
// Only the DOM-dependent TipTap command facade is replaced.
export function createTestEditor(text = 'Original text') {
  const editor = {
    isDestroyed: false,
    state: EditorState.create({ schema, doc: schema.node('doc', null, [schema.node('paragraph', null, schema.text(text))]), plugins: [history()] }),
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
        setTextSelection(selection) { tr = tr.setSelection(TextSelection.create(tr.doc, selection.from ?? selection, selection.to ?? selection)); return chain; },
        setLink(attrs) { tr = tr.addMark(tr.selection.from, tr.selection.to, schema.marks.link.create(attrs)); return chain; },
        unsetLink() { tr = tr.removeMark(tr.selection.from, tr.selection.to, schema.marks.link); return chain; },
        insertAiBlock(attrs) { tr = tr.replaceRangeWith(tr.selection.from, tr.selection.to, schema.node('aiBlock', attrs)); return chain; },
        insertContentAt(range, json) { tr = tr.replaceRangeWith(range.from ?? range, range.to ?? range, schema.nodeFromJSON(json)); return chain; },
        run() { editor.view.dispatch(tr); return true; },
      };
      return chain;
    },
  };
  return editor;
}
