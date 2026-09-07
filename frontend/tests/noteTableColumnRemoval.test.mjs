import test from 'node:test';
import assert from 'node:assert/strict';
import { shallowRef } from 'vue';
import { Schema } from '@tiptap/pm/model';
import { EditorState, TextSelection } from '@tiptap/pm/state';
import { tableNodes, deleteColumn } from '@tiptap/pm/tables';
import { history, undo } from '@tiptap/pm/history';
import { useNoteTables } from '../src/components/notes/composables/useNoteTables.js';
import { mountController } from './helpers/noteEditorHarness.mjs';

for (const column of [0, 1, 2]) {
  test(`table handle preserves column ${column + 1}, deletes it and supports undo`, (t) => {
    const previousElement = globalThis.Element;
    class FakeElement {
      closest() { return this; }
      contains() { return true; }
      getBoundingClientRect() { return { left: 40, top: 20, width: 600 }; }
      querySelector() { return this; }
    }
    globalThis.Element = FakeElement;
    t.after(() => { globalThis.Element = previousElement; });
    const wrapper = new FakeElement();
    const schema = new Schema({ nodes: {
      doc: { content: 'block+' }, paragraph: { content: 'text*', group: 'block' }, text: {},
      ...tableNodes({ tableGroup: 'block', cellContent: 'paragraph+' }),
    } });
    const table = schema.node('table', null, ['ABC', 'DEF'].map(row => schema.node('table_row', null,
      [...row].map(text => schema.node('table_cell', null, schema.node('paragraph', null, schema.text(text)))))));
    const doc = schema.node('doc', null, table);
    let position;
    doc.descendants((node, pos) => { if (node.isText && node.text === 'ABC'[column]) position = pos; });
    let state = EditorState.create({ schema, doc, selection: TextSelection.create(doc, position), plugins: [history()] });
    const dispatch = tr => { state = state.apply(tr); };
    const editor = {
      get state() { return state; }, isActive: () => true,
      view: { domAtPos: () => ({ node: wrapper }), posAtDOM: () => 4 },
      chain() {
        let command = () => true;
        const chain = { focus: () => chain,
          setTextSelection(pos) { dispatch(state.tr.setSelection(TextSelection.create(doc, pos))); return chain; },
          deleteColumn() { command = () => deleteColumn(state, dispatch); return chain; },
          run: () => command(),
        };
        return chain;
      },
    };
    const { controller, unmount } = mountController(() => useNoteTables({
      editor: shallowRef(editor), surfaceEl: shallowRef(wrapper), props: { noteId: 'test' },
      overlays: { register() {}, open() {} }, clampMenuLeft: left => left,
    }));
    t.after(unmount);
    controller.refreshTableHandle();
    controller.openTableMenuFromHandle();
    assert.equal(state.selection.from, position);
    controller.runTableCommand('deleteColumn');
    assert.equal(state.doc.firstChild.firstChild.childCount, 2);
    assert.equal(state.doc.textContent, ['ABC', 'DEF'].map(row => [...row].filter((_, i) => i !== column).join('')).join(''));
    assert.ok(undo(state, dispatch));
    assert.ok(state.doc.eq(doc));
  });
}
