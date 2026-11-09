import { test } from 'node:test';
import assert from 'node:assert/strict';
import { findCorrespondentSuggestions } from '../src/utils/correspondentSuggestions.js';
const items = [
  { id: 'garage', name: 'Wiker Autoservice', aliases: [{ alias: 'Wiker Werkstatt' }] },
  { id: 'other', name: 'Andere Firma', aliases: [] },
];
test('hyphens and spaces suggest an existing correspondent without claiming identity', () => {
  const matches = findCorrespondentSuggestions(items, 'Wiker-Auto-Service');
  assert.equal(matches.length, 1);
  assert.equal(matches[0].correspondent.id, 'garage');
  assert.equal(matches[0].exact, false);
});
test('exact names and aliases ignore case and repeated whitespace', () => {
  assert.equal(findCorrespondentSuggestions(items, ' WIKER   AUTOSERVICE ')[0].exact, true);
  assert.equal(findCorrespondentSuggestions(items, 'wiker werkstatt')[0].exact, true);
});
test('unicode names compare consistently', () => {
  assert.equal(findCorrespondentSuggestions([{ name: 'Möller' }], 'Mo\u0308ller')[0].exact, true);
});
test('short fragments and unrelated names produce no suggestions', () => {
  assert.deepEqual(findCorrespondentSuggestions(items, 'W'), []);
  assert.deepEqual(findCorrespondentSuggestions(items, 'TSV'), []);
  assert.deepEqual(findCorrespondentSuggestions(items, 'Neue Firma'), []);
});
test('all exact matches are retained before similar matches', () => {
  const matches = findCorrespondentSuggestions([...items, { id: 'alias', name: 'Werkstatt', aliases: [{ alias: 'Wiker Autoservice' }] }], 'Wiker Autoservice');
  assert.equal(matches.filter(m => m.exact).length, 2);
});
test('a different or missing legal form ranks right after exact matches', () => {
  const list = [
    { id: 'similar', name: 'Vodafone Kabel', aliases: [] },
    { id: 'vodafone', name: 'Vodafone GmbH', aliases: [] },
  ];
  const matches = findCorrespondentSuggestions(list, 'Vodafone');
  assert.equal(matches[0].correspondent.id, 'vodafone');
  assert.equal(matches[0].exact, false);
  assert.equal(matches[0].legalFormOnly, true);
  assert.equal(findCorrespondentSuggestions(list, 'vodafone gmbh')[0].exact, true);
  assert.equal(findCorrespondentSuggestions([{ name: 'Wiker Autoservice' }], 'Wiker Autoservice GmbH & Co. KG')[0].legalFormOnly, true);
});
test('conflicting legal forms stay a plain suggestion', () => {
  const [match] = findCorrespondentSuggestions([{ name: 'Müller GmbH' }], 'Müller KG');
  assert.equal(match.legalFormOnly, false);
  assert.equal(match.exact, false);
});
