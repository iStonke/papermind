import assert from 'node:assert/strict';
import test from 'node:test';

import { groupNotesByCreationDay } from '../src/utils/noteDateGroups.js';

test('notes are grouped by their creation day with newest days first', () => {
  const notes = [
    { id: 'older', created_at: '2026-08-22T20:00:00+02:00', updated_at: '2026-08-24T10:00:00+02:00' },
    { id: 'newer-a', created_at: '2026-08-24T08:00:00+02:00' },
    { id: 'newer-b', created_at: '2026-08-24T07:00:00+02:00' },
  ];

  const groups = groupNotesByCreationDay(notes, new Date('2026-08-24T12:00:00+02:00'));

  assert.deepEqual(groups.map((group) => group.label), ['Heute', 'Samstag, 22. August']);
  assert.deepEqual(groups[0].notes.map((note) => note.id), ['newer-a', 'newer-b']);
  assert.deepEqual(groups[1].notes.map((note) => note.id), ['older']);
});

test('yesterday and missing creation dates get useful group labels', () => {
  const notes = [
    { id: 'missing' },
    { id: 'yesterday', created_at: '2026-08-23T17:30:00+02:00' },
  ];

  const groups = groupNotesByCreationDay(notes, new Date('2026-08-24T12:00:00+02:00'));

  assert.deepEqual(groups.map((group) => group.label), ['Gestern', 'Ohne Erstellungsdatum']);
});
