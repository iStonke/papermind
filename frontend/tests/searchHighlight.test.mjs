import assert from 'node:assert/strict';
import test from 'node:test';
import { centerOnMatch, highlightParts } from '../src/utils/searchHighlight.js';

test('highlightParts marks every query term case-insensitively', () => {
  assert.deepEqual(highlightParts('Testfall und TEST', 'test'), [
    { text: 'Test', match: true },
    { text: 'fall und ', match: false },
    { text: 'TEST', match: true },
  ]);
  assert.deepEqual(highlightParts('ohne', ''), [{ text: 'ohne', match: false }]);
});

test('centerOnMatch keeps the first match close to the start of the excerpt', () => {
  const long = `${'Einleitung '.repeat(12)}hier steht der Testfall am Ende`;
  const centered = centerOnMatch(long, 'testfall', 20);
  assert.ok(centered.startsWith('…'));
  assert.ok(centered.toLowerCase().indexOf('testfall') <= 22);
  assert.equal(centerOnMatch('Testfall vorne', 'testfall'), 'Testfall vorne');
  assert.equal(centerOnMatch('kein Treffer', 'xyz'), 'kein Treffer');
});
