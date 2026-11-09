import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cleanupSuggestionCount, findCleanupSuggestions } from '../src/utils/correspondentCleanup.js';
import { findDuplicatePairs } from '../src/utils/correspondentDuplicates.js';

const items = [
  { id: 'a', name: 'Vodafone GmbH', kind: 'organization', usage_count: 12 },
  { id: 'b', name: 'Vodafone', kind: 'organization', usage_count: 0 },
  { id: 'c', name: 'Techem GmbH', kind: 'organization', short_name: 'Techem', usage_count: 3 },
  { id: 'd', name: 'Energie GmbH', kind: 'collection', usage_count: 0 },
  { id: 'e', name: 'Hausverwaltung', kind: 'organization', usage_count: 0 },
  { id: 'f', name: 'Alex Bauer', kind: 'person', parent_id: 'e', usage_count: 2 },
  { id: 'g', name: 'Unbekannt AG', kind: 'organization' },
];
const membersOf = id => items.filter(item => item.parent_id === id);

test('cleanup finds missing short names and safe empties', () => {
  const result = findCleanupSuggestions(items, membersOf);
  assert.deepEqual(result.shortNames.map(entry => [entry.id, entry.suggestion]), [['g', 'Unbekannt'], ['a', 'Vodafone']]);
  // Collections never get short names; entries with members or unknown counts are not "empty".
  assert.deepEqual(result.empties.map(entry => entry.id), ['d', 'b']);
  assert.equal(cleanupSuggestionCount(result), 4);
});
test('duplicate pairs appear once, alphabetically, and can be dismissed', () => {
  const pairs = findDuplicatePairs(items);
  assert.deepEqual(pairs.map(pair => [pair.key, pair.a.name, pair.b.name, pair.reason]), [['a|b', 'Vodafone', 'Vodafone GmbH', 'legalForm']]);
  assert.deepEqual(findDuplicatePairs(items, ['a|b']), []);
});
