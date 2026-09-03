import assert from 'node:assert/strict';
import test from 'node:test';

import {
  CLEANUP_INSTRUCTION,
  CLEANUP_INPUT_LIMIT,
  cleanupMarker,
  formatCleanupInput,
  parseCleanupOutput,
  stripCleanupMarks,
} from '../src/utils/noteCleanup.js';

test('input formatting numbers each block and flattens stray whitespace', () => {
  const input = formatCleanupInput(['budget q3 noch offen', 'launch\n  verschoben']);
  assert.equal(input, '⟦1⟧ budget q3 noch offen\n\n⟦2⟧ launch verschoben');
  assert.equal(cleanupMarker(3), '⟦3⟧');
});

test('the cleanup instruction carries the meaning-preserving guardrails', () => {
  assert.match(CLEANUP_INSTRUCTION, /Erfinde NICHTS/);
  assert.match(CLEANUP_INSTRUCTION, /\[unklar\]/);
  assert.match(CLEANUP_INSTRUCTION, /Reihenfolge/);
  assert.match(CLEANUP_INSTRUCTION, /⟦n⟧/);
  // Muss unter das 2000-Zeichen-Limit des Backend-Anweisungsfelds passen.
  assert.ok(CLEANUP_INSTRUCTION.length < 2000);
  assert.ok(CLEANUP_INPUT_LIMIT < 8000);
});

test('a well-formed multi-block answer maps back one to one', () => {
  const raw = '⟦1⟧ Das Budget für Q3 ist noch offen.\n⟦2⟧ Der Launch wird verschoben.';
  const { ok, blocks } = parseCleanupOutput(raw, 2);
  assert.equal(ok, true);
  assert.deepEqual(blocks, [
    'Das Budget für Q3 ist noch offen.',
    'Der Launch wird verschoben.',
  ]);
});

test('leading chatter before the first marker is ignored', () => {
  const raw = 'Gerne! ⟦1⟧ Ausformulierter Satz.';
  const { ok, blocks } = parseCleanupOutput(raw, 1);
  assert.equal(ok, true);
  assert.deepEqual(blocks, ['Ausformulierter Satz.']);
});

test('a mismatched block count fails safe so nothing gets garbled', () => {
  // Modell liefert nur einen von zwei erwarteten Blöcken.
  assert.equal(parseCleanupOutput('⟦1⟧ Nur ein Block.', 2).ok, false);
  // Marker fehlt völlig.
  assert.equal(parseCleanupOutput('Ein Fließtext ohne Marker.', 1).ok, false);
  // Leerer Block wird verworfen.
  assert.equal(parseCleanupOutput('⟦1⟧   \n⟦2⟧ Text', 2).ok, false);
});

test('preview stripping removes markers and collapses blank runs', () => {
  const preview = stripCleanupMarks('⟦1⟧ Erster Satz.\n\n\n⟦2⟧ Zweiter Satz.');
  assert.equal(preview, 'Erster Satz.\n\nZweiter Satz.');
});
