import test from 'node:test';
import assert from 'node:assert/strict';
import { sortNoteItems } from '../src/utils/noteSort.js';
const notes = [
  { id: 'b', title: 'Banane', created_at: '2026-01-01', updated_at: '2026-03-01' },
  { id: 'a', title: 'Apfel', created_at: '2026-03-01', updated_at: '2026-02-01' },
  { id: 'c', title: 'Zitrone', created_at: '2026-02-01', updated_at: '2026-01-01' },
];
for (const [mode, expected] of [['title', ['a', 'b', 'c']], ['created', ['a', 'c', 'b']], ['updated', ['b', 'a', 'c']]]) {
  test(`${mode} sorts in both directions without modifying the source`, () => {
    assert.deepEqual(sortNoteItems(notes, mode).map(n => n.id), expected);
    assert.deepEqual(sortNoteItems(notes, mode, true).map(n => n.id), [...expected].reverse());
    assert.deepEqual(notes.map(n => n.id), ['b', 'a', 'c']);
  });
}
