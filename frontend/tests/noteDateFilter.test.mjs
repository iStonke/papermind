import test from 'node:test';
import assert from 'node:assert/strict';
import { noteMatchesDateRange } from '../src/utils/noteDateFilter.js';
const now = new Date(2026, 8, 7, 13);
const note = (day, hour = 12) => ({ updated_at: new Date(2026, 8, day, hour).toISOString() });
test('periods include their first local calendar day and exclude earlier and future days', () => {
  assert.equal(noteMatchesDateRange(note(7, 0), 'today', now), true);
  assert.equal(noteMatchesDateRange(note(6), 'today', now), false);
  assert.equal(noteMatchesDateRange(note(1, 0), 'last_7_days', now), true);
  assert.equal(noteMatchesDateRange(note(0), 'last_7_days', now), false);
  assert.equal(noteMatchesDateRange(note(8), 'last_7_days', now), false);
  assert.equal(noteMatchesDateRange(note(-22, 0), 'last_30_days', now), true);
  assert.equal(noteMatchesDateRange(note(-23), 'last_30_days', now), false);
});
test('all periods includes missing dates; active filters omit invalid dates', () => {
  assert.equal(noteMatchesDateRange({}, '', now), true);
  assert.equal(noteMatchesDateRange({updated_at:'invalid'}, 'today', now), false);
});
