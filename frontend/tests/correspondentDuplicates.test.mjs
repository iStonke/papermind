import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canMergeCorrespondents, findDuplicateCandidates, preferredMergeTarget } from '../src/utils/correspondentDuplicates.js';

const items = [
  { id: 'a', name: 'Vodafone', kind: 'organization', usage_count: 2, aliases: [] },
  { id: 'b', name: 'Vodafone GmbH', kind: 'organization', usage_count: 12, aliases: [] },
  { id: 'c', name: 'Vodafone Kabel', kind: 'organization', usage_count: 4, aliases: [] },
  { id: 'd', name: 'Wiker Autoservice', kind: null, usage_count: 1, aliases: [] },
  { id: 'e', name: 'Wiker-Auto-Service', kind: 'organization', usage_count: 0, aliases: [] },
  { id: 'f', name: 'Werkstatt', kind: 'organization', usage_count: 0, aliases: [{ alias: 'Vodafone' }] },
  { id: 'g', name: 'Vodafone', kind: 'person', usage_count: 0, aliases: [] },
];
const byId = id => items.find(item => item.id === id);

test('legal form, spelling and alias matches count as duplicates, partial matches do not', () => {
  const found = findDuplicateCandidates(items, byId('a'));
  assert.deepEqual(found.map(match => [match.correspondent.id, match.reason]), [['f', 'alias'], ['b', 'legalForm']]);
  assert.deepEqual(findDuplicateCandidates(items, byId('d')).map(match => match.reason), ['spelling']);
});
test('different kinds are never offered; untyped entries match any kind', () => {
  assert.equal(canMergeCorrespondents(byId('a'), byId('g')), false);
  assert.equal(canMergeCorrespondents(byId('d'), byId('e')), true);
  assert.equal(canMergeCorrespondents(byId('a'), byId('a')), false);
  assert.ok(!findDuplicateCandidates(items, byId('a')).some(match => match.correspondent.id === 'g'));
});
test('the entry with more documents stays by default', () => {
  assert.equal(preferredMergeTarget(byId('a'), byId('b')).id, 'b');
  assert.equal(preferredMergeTarget(byId('b'), byId('a')).id, 'b');
  assert.equal(preferredMergeTarget(byId('e'), byId('f')).id, 'e');
});
