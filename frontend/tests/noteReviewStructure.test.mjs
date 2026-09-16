import assert from 'node:assert/strict';
import test from 'node:test';
import { createTestEditor } from './helpers/noteEditorHarness.mjs';
import { reviewStructureContext, flattenReviewDoc, resolveReviewPositions, planReviewEdits, applyReviewEdits, reviewChangesStillValid } from '../src/components/notes/composables/noteReviewDoc.js';
import { parseReviewOutput, resolveReviewAnchors } from '../src/utils/noteReview.js';
const paragraph = text => ({ type: 'paragraph', content: [{ type: 'text', text }] });
function editor() { return createTestEditor('', { type: 'doc', content: [paragraph('Davor'), paragraph('Name: Anna'), paragraph('Rolle: Leitung'), paragraph('Danach')] }); }
function resolve(ed, change) {
  const { text, map } = flattenReviewDoc(ed.state.doc);
  return resolveReviewPositions(ed.state.doc, map, resolveReviewAnchors(text, [change]))[0];
}
const change = { id: 1, cat: 'format', blockIds: ['b2', 'b3'], anchor: 'Name: Anna\nRolle: Leitung', revised: '| Name | Rolle |\n| --- | --- |\n| Anna | Leitung |' };

test('structure context carries existing heading and callout types and only safe metadata', () => {
  const ed = createTestEditor('', { type: 'doc', content: [{ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Titel', marks: [{type:'bold'}] }] }, { type: 'callout', attrs: { kind: 'important' }, content: [paragraph('Hinweis')] }] });
  const blocks = reviewStructureContext(ed.state.doc);
  assert.equal(blocks[0].structure[0].level, 2);
  assert.equal(blocks[1].structure[0].kind, 'important');
  assert.deepEqual(blocks[0].structure[1].marks, ['bold']);
  assert.equal(blocks[0].json, undefined);
});

for (const [kind, revised] of [
  ['table', change.revised],
  ['callout', '> [!INFO]\n> Name: Anna\n> Rolle: Leitung'],
  ['paragraph', 'Anna übernimmt die Leitung.'],
  ['taskList', '- [ ] Name: Anna\n- [ ] Rolle: Leitung'],
]) {
  test(`converts complete adjacent paragraphs to ${kind}, preserves neighbors and supports undo`, () => {
    const ed = editor();
    const before = ed.state.doc.toJSON();
    const target = resolve(ed, { ...change, revised });
    assert.equal(target.found, true);
    const { edits } = planReviewEdits([target]);
    assert.equal(edits.length, 1);
    applyReviewEdits(ed, edits);
    assert.equal(ed.state.doc.childCount, 3);
    assert.equal(ed.state.doc.child(1).type.name, kind);
    assert.equal(ed.state.doc.firstChild.textContent, 'Davor');
    assert.equal(ed.state.doc.lastChild.textContent, 'Danach');
    ed.commands.undo();
    assert.deepEqual(ed.state.doc.toJSON(), before);
  });
}

test('rejects partial anchors, unknown IDs, nonadjacent and reordered blocks', () => {
  for (const altered of [{ anchor: 'Anna' }, { blockIds: ['b99'] }, { blockIds: ['b2', 'b4'] }, { blockIds: ['b3', 'b2'] }]) {
    assert.equal(resolve(editor(), { ...change, ...altered }).found, false);
  }
});

test('source snapshots detect edits and relocate unchanged targets after earlier changes', () => {
  const ed = editor();
  const target = resolve(ed, change);
  ed.chain().insertContentAt(1, {type:'text',text:'Zusatz '}).run();
  assert.equal(reviewChangesStillValid(ed.state.doc, [target]), false);
  const relocated = resolve(ed, target);
  assert.equal(relocated.found, true);
  assert.equal(reviewChangesStillValid(ed.state.doc, [relocated]), true);
  ed.chain().insertContentAt(relocated.from, {type:'text',text:'Geändert '}).run();
  assert.equal(resolve(ed, relocated).found, false);
});

test('legacy partial structural replacement cannot erase unanchored text', () => {
  const ed = createTestEditor('Vorher wichtig nachher');
  const target = resolve(ed, { id:1, cat:'format', anchor:'wichtig', revised:'## Wichtig' });
  assert.equal(planReviewEdits([target]).edits.length, 0);
});

test('structured IDs are accepted only for formatting', () => {
  const raw = {cat:'format',anchor:'Text',revised:'> [!INFO]\n> Text',block_ids:['b1']};
  assert.deepEqual(parseReviewOutput(JSON.stringify({changes:[raw]})).changes[0].blockIds,['b1']);
  assert.equal(parseReviewOutput(JSON.stringify({changes:[{...raw,cat:'add'}]})).ok,false);
});

test('formatting refuses blocks containing links or completed tasks', () => {
  for (const node of [
    { type: 'paragraph', content: [{ type: 'text', text: 'Quelle', marks: [{type:'link',attrs:{href:'https://example.com'}}] }] },
    { type: 'taskList', content: [{type:'taskItem',attrs:{checked:true},content:[paragraph('Erledigt')]}] },
    { type: 'aiBlock', attrs:{text:'Erzeugt'} },
  ]) {
    const ed = createTestEditor('',{type:'doc',content:[node]});
    const [block] = reviewStructureContext(ed.state.doc);
    assert.equal(block.convertible,false);
    assert.equal(resolve(ed,{...change,blockIds:['b1'],anchor:block.text}).found,false);
  }
});

test('lists can become prose without leaving list wrappers behind', () => {
  const ed=createTestEditor('',{type:'doc',content:[{type:'bulletList',content:[{type:'listItem',content:[paragraph('Anna')]},{type:'listItem',content:[paragraph('Leitung')]}]},paragraph('Danach')]});
  const before=ed.state.doc.toJSON();
  const target=resolve(ed,{...change,blockIds:['b1'],anchor:'Anna\nLeitung',revised:'Anna übernimmt die Leitung.'});
  applyReviewEdits(ed,planReviewEdits([target]).edits);
  assert.equal(ed.state.doc.firstChild.type.name,'paragraph');
  assert.equal(ed.state.doc.lastChild.textContent,'Danach');
  ed.commands.undo();
  assert.deepEqual(ed.state.doc.toJSON(),before);
});

test('shrinking a document makes an old structural snapshot invalid without throwing', () => {
  const ed=editor();
  const target=resolve(ed,change);
  const empty=createTestEditor('');
  assert.equal(reviewChangesStillValid(empty.state.doc,[target]),false);
});
