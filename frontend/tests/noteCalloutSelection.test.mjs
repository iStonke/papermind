import assert from 'node:assert/strict';
import test from 'node:test';
import { Schema } from '@tiptap/pm/model';
import { EditorState, TextSelection } from '@tiptap/pm/state';
import { history, undo } from '@tiptap/pm/history';
import { replaceSelectionWithCallout } from '../src/components/notes/nodes/calloutSelection.js';

const schema = new Schema({ nodes: {
  doc: { content: 'block+' }, text: { group: 'inline' },
  paragraph: { content: 'inline*', group: 'block' },
  callout: { content: 'block+', group: 'block', attrs: { kind: { default: 'info' } } },
  bulletList: { content: 'listItem+', group: 'block' },
  listItem: { content: 'paragraph block*' },
}, marks: { bold: {} } });
const p = (text) => schema.node('paragraph', null, text ? schema.text(text) : null);
function convert(doc, from, to) {
  const state = EditorState.create({ doc, selection: TextSelection.create(doc, from, to), plugins: [history()] });
  const tr = state.tr;
  assert.equal(replaceSelectionWithCallout(tr, schema.nodes.callout, { kind: 'question' }), true);
  const result = state.apply(tr);
  result.doc.check();
  let restored;
  assert.equal(undo(result, tr => { restored = result.apply(tr).doc; }), true);
  assert.deepEqual(restored.toJSON(), doc.toJSON());
  return result.doc;
}
test('selected paragraph moves into a callout without deleting or duplicating its text', () => {
  const doc = schema.node('doc', null, [p('Before'), p('Selected'), p('After')]);
  const result = convert(doc, 9, 17);
  assert.deepEqual(result.toJSON(), schema.node('doc', null, [p('Before'), schema.node('callout', { kind: 'question' }, p('Selected')), p('After')]).toJSON());
});
test('partial selection preserves surrounding text and bold marks', () => {
  const doc = schema.node('doc', null, schema.node('paragraph', null, [schema.text('Before '), schema.text('selected', [schema.mark('bold')]), schema.text(' after')]));
  const result = convert(doc, 8, 16);
  assert.equal(result.child(0).textContent, 'Before ');
  assert.equal(result.child(1).type.name, 'callout');
  assert.equal(result.child(1).textContent, 'selected');
  assert.equal(result.child(1).firstChild.firstChild.marks[0].type.name, 'bold');
  assert.equal(result.child(2).textContent, ' after');
});
test('multiple paragraphs retain their boundaries', () => {
  const doc = schema.node('doc', null, [p('One'), p('Two')]);
  const result = convert(doc, 1, 9);
  assert.equal(result.firstChild.type.name, 'callout');
  assert.equal(result.firstChild.childCount, 2);
  assert.equal(result.textContent, 'OneTwo');
});
test('a selected list retains its structure', () => {
  const list = schema.node('bulletList', null, ['One', 'Two'].map(text => schema.node('listItem', null, p(text))));
  const doc = schema.node('doc', null, list);
  const result = convert(doc, 3, 13);
  assert.equal(result.firstChild.type.name, 'callout');
  assert.deepEqual(result.firstChild.firstChild.toJSON(), list.toJSON());
});
test('an empty selection does not replace content', () => {
  const doc = schema.node('doc', null, p('Keep'));
  const tr = EditorState.create({doc}).tr;
  assert.equal(replaceSelectionWithCallout(tr, schema.nodes.callout, {}), false);
  assert.equal(tr.docChanged, false);
});
