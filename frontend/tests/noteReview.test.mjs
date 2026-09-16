import assert from 'node:assert/strict';
import test from 'node:test';

import {
  NOTE_REVIEW_INPUT_LIMIT,
  REVIEW_CATEGORIES,
  parseReviewOutput,
  resolveReviewAnchors,
  reviewDefaultAccepted,
  summarizeReviewChanges,
} from '../src/utils/noteReview.js';

test('input limit stays under the backend note_text cap of 12000', () => {
  assert.ok(NOTE_REVIEW_INPUT_LIMIT < 12000);
  assert.deepEqual(REVIEW_CATEGORIES, ['fix', 'format', 'add']);
});

test('fix and format are pre-accepted, add is opt-in', () => {
  assert.equal(reviewDefaultAccepted({ cat: 'fix' }), true);
  assert.equal(reviewDefaultAccepted({ cat: 'format' }), true);
  assert.equal(reviewDefaultAccepted({ cat: 'add' }), false);
});

test('parses a clean change list and keeps categories honest', () => {
  const raw = JSON.stringify({
    changes: [
      { id: 1, cat: 'format', anchor: 'meeting 12.03 mit holger', revised: '# Meeting 12.03. – Holger', reason: 'Titel.' },
      { id: 2, cat: 'fix', anchor: 'matstammdaten', revised: 'Materialstammdaten', reason: 'Abk.' },
      { id: 3, cat: 'add', anchor: 'preise klaeren', revised: 'Offener Punkt: Preise klären.', reason: 'vage', confidence: 'niedrig', insert_before: false },
    ],
  });
  const { ok, changes, error } = parseReviewOutput(raw);
  assert.equal(ok, true);
  assert.equal(error, '');
  assert.equal(changes.length, 3);
  assert.equal(changes[2].confidence, 'niedrig');
  assert.equal(changes[2].insertBefore, false);
});

test('tolerates a ```json fence and surrounding prose', () => {
  const raw = 'Hier das Ergebnis:\n```json\n{"changes":[{"id":1,"cat":"fix","anchor":"foo","revised":"Foo","reason":"x"}]}\n```\nFertig.';
  const { ok, changes } = parseReviewOutput(raw);
  assert.equal(ok, true);
  assert.equal(changes.length, 1);
  assert.equal(changes[0].revised, 'Foo');
});

test('falls back to the first balanced object when JSON.parse fails on wrapper', () => {
  const raw = 'noise {"changes":[{"id":1,"cat":"fix","anchor":"a","revised":"A","reason":""}]} trailing';
  const { ok, changes } = parseReviewOutput(raw);
  assert.equal(ok, true);
  assert.equal(changes.length, 1);
});

test('drops invalid entries: unknown category, empty anchor, missing revised', () => {
  const { changes } = parseReviewOutput(JSON.stringify({
    changes: [
      { id: 1, cat: 'delete', anchor: 'x', revised: 'y', reason: '' },
      { id: 2, cat: 'fix', anchor: '   ', revised: 'y', reason: '' },
      { id: 3, cat: 'fix', anchor: 'ok', revised: '', reason: '' },
      { id: 4, cat: 'fix', anchor: 'keep', revised: 'Keep', reason: 'r' },
    ],
  }));
  assert.equal(changes.length, 1);
  assert.equal(changes[0].anchor, 'keep');
});

test('add without confidence defaults to niedrig (stays opt-in)', () => {
  const { changes } = parseReviewOutput(JSON.stringify({
    changes: [{ id: 1, cat: 'add', anchor: 'a', revised: 'Ergänzung', reason: 'r' }],
  }));
  assert.equal(changes[0].confidence, 'niedrig');
});

test('rejects non-JSON and missing change lists', () => {
  assert.equal(parseReviewOutput('not json at all').ok, false);
  assert.equal(parseReviewOutput('{"foo":1}').ok, false);
});

test('duplicate ids are forced apart into distinct running numbers', () => {
  const { changes } = parseReviewOutput(JSON.stringify({
    changes: [
      { id: 1, cat: 'fix', anchor: 'a', revised: 'A', reason: '' },
      { id: 1, cat: 'fix', anchor: 'b', revised: 'B', reason: '' },
    ],
  }));
  assert.notEqual(changes[0].id, changes[1].id);
});

test('resolves anchors to character ranges', () => {
  const text = 'meeting mit holger';
  const [change] = resolveReviewAnchors(text, [{ cat: 'fix', anchor: 'holger' }]);
  assert.equal(change.found, true);
  assert.equal(change.charFrom, 12);
  assert.equal(change.charTo, 18);
  assert.equal(text.slice(change.charFrom, change.charTo), 'holger');
});

test('multiple occurrences of the same anchor resolve in order of the changes', () => {
  const text = 'preis offen. später nochmal preis prüfen.';
  const resolved = resolveReviewAnchors(text, [
    { id: 1, cat: 'fix', anchor: 'preis' },
    { id: 2, cat: 'fix', anchor: 'preis' },
  ]);
  assert.equal(resolved[0].charFrom, text.indexOf('preis'));
  assert.equal(resolved[1].charFrom, text.indexOf('preis', text.indexOf('preis') + 1));
  assert.notEqual(resolved[0].charFrom, resolved[1].charFrom);
});

test('surplus changes on a single occurrence share the last (same-span) match', () => {
  const text = 'ausserdem preise klaeren';
  const resolved = resolveReviewAnchors(text, [
    { id: 1, cat: 'fix', anchor: 'ausserdem preise klaeren' },
    { id: 2, cat: 'add', anchor: 'ausserdem preise klaeren' },
  ]);
  assert.equal(resolved[0].charFrom, 0);
  assert.equal(resolved[1].charFrom, 0);
});

test('unfound anchors are flagged rather than mislocated', () => {
  const [change] = resolveReviewAnchors('hello world', [{ cat: 'fix', anchor: 'missing' }]);
  assert.equal(change.found, false);
  assert.equal(change.charFrom, -1);
});

test('summary counts auto vs add among found changes only', () => {
  const summary = summarizeReviewChanges([
    { found: true, cat: 'fix' },
    { found: true, cat: 'format' },
    { found: true, cat: 'add' },
    { found: false, cat: 'fix' },
  ]);
  assert.deepEqual(summary, { auto: 2, add: 1, total: 3 });
});

test('extracts balanced JSON despite unrelated braces and preserves string contents', () => {
  const entry = { id: 1, cat: 'fix', anchor: 'Text {a}, ]', revised: 'Zitat "x" und \\Pfad, }', reason: 'r' };
  const result = parseReviewOutput('Hinweis {kein JSON}\n```JSON\n' + JSON.stringify({ changes: [entry] }) + '\n```\nEnde {ok}');
  assert.equal(result.ok, true);
  assert.equal(result.changes[0].anchor, entry.anchor);
  assert.equal(result.changes[0].revised, entry.revised);
});

test('tolerates trailing commas without modifying comma-like text inside strings', () => {
  const result = parseReviewOutput('{"changes":[{"cat":"fix","anchor":"a, }","revised":"b, ]",},],}');
  assert.equal(result.ok, true);
  assert.equal(result.changes[0].anchor, 'a, }');
  assert.equal(result.changes[0].revised, 'b, ]');
});

test('rejects truncated output rather than silently accepting a partial list', () => {
  for (const raw of [
    '{"changes":[{"cat":"fix","anchor":"a","revised":"b"}',
    '{"changes":[{"cat":"fix","anchor":"a","revised":"b"},{"cat":"fix","anchor":"c","revised":"unfertig',
    '{"changes":[{"cat":"fix","anchor":"a","revised":"Zitat "kaputt""}]}',
  ]) assert.equal(parseReviewOutput(raw).ok, false);
});

test('a list of invalid entries is an error, not a successful empty review', () => {
  assert.equal(parseReviewOutput('{"changes":[{"cat":"unknown"}]}').ok, false);
  assert.equal(parseReviewOutput('{"changes":[]}').ok, true);
});


test('compact descriptions preserve the full replacement and support older responses', () => {
  const entry = {id:1,cat:'fix',anchor:'alt',revised:'Vollständiger neuer Inhalt',reason:'Ältere Begründung'};
  const parse = extra => parseReviewOutput(JSON.stringify({changes:[{...entry,...extra}]})).changes[0];
  assert.equal(parse({summary:'  Die Schreibweise korrigieren.  '}).summary, 'Die Schreibweise korrigieren.');
  assert.equal(parse({}).summary, entry.reason);
  assert.equal(parse({summary:'x'.repeat(300)}).summary.length, 200);
  assert.equal(parse({summary:'x'.repeat(300)}).revised, entry.revised);
  assert.ok(parse({reason:''}).summary.length > 0);
});
