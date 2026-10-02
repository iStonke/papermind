import test from 'node:test';
import assert from 'node:assert/strict';
import { sortThoughts } from '../src/utils/thoughtSort.js';
const items = [
  { id:'a', text:'Gedanke 10\nA', created_at:'2026-01-01', updated_at:'2026-01-03' },
  { id:'b', text:'gedanke 2\nZ', created_at:'2026-01-02', updated_at:'2026-01-02' },
];
test('sorts creation and modification independently without mutating input', () => {
  assert.deepEqual(sortThoughts(items).map(x => x.id), ['b','a']);
  assert.deepEqual(sortThoughts(items,'updated_at','desc').map(x => x.id), ['a','b']);
  assert.deepEqual(sortThoughts(items,'created_at','asc').map(x => x.id), ['a','b']);
  assert.equal(items[0].id,'a');
});
test('title sorting uses natural German ordering and supports both directions', () => {
  assert.deepEqual(sortThoughts(items,'title','asc').map(x => x.id), ['b','a']);
  assert.deepEqual(sortThoughts(items,'title','desc').map(x => x.id), ['a','b']);
});

test('color sorting groups default and explicit sage, normalizes case and reverses palette order', () => {
  const notes = [
    { id:'d', title_color:'#CBDFF1' }, { id:'c', title_color:'#d9dfe2' },
    { id:'b', title_color:'#cce0dc' }, { id:'a', title_color:null },
  ];
  assert.deepEqual(sortThoughts(notes,'color','asc').map(x => x.id), ['a','b','d','c']);
  assert.deepEqual(sortThoughts(notes,'color','desc').map(x => x.id), ['c','d','a','b']);
});
