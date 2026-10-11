import test from 'node:test';
import assert from 'node:assert/strict';
import { createTestEditor } from './helpers/noteEditorHarness.mjs';
import {
  computeNoteStats, countSyllables, fleschAmstad, readabilityBand, splitSentences,
} from '../src/utils/noteStats.js';

const paragraphs = (...texts) => ({ type: 'doc', content: texts.map(text => ({
  type: 'paragraph', content: text ? [{ type: 'text', text }] : [],
})) });

test('sentence split keeps German abbreviations and ordinals together', () => {
  const text = 'Das ist z. B. ein Test am 3. Oktober. Dr. Müller kommt! Wirklich? Ja.';
  const sentences = splitSentences(text).map(r => text.slice(r.start, r.end).trim());
  assert.deepEqual(sentences, [
    'Das ist z. B. ein Test am 3. Oktober.',
    'Dr. Müller kommt!',
    'Wirklich?',
    'Ja.',
  ]);
});

test('counts words, characters, sentences and paragraphs across blocks', () => {
  const { state } = createTestEditor('', paragraphs('Eins zwei drei. Vier fünf.', '', 'Sechs sieben'));
  const stats = computeNoteStats(state.doc);
  assert.equal(stats.words, 7);
  assert.equal(stats.sentences, 3);
  assert.equal(stats.paragraphs, 2);
  assert.equal(stats.characters, 'Eins zwei drei. Vier fünf.'.length + 'Sechs sieben'.length);
  assert.equal(stats.charactersNoSpaces, 'Einszweidrei.Vierfünf.Sechssieben'.length);
  assert.equal(stats.selection, false);
  assert.equal(stats.readingMinutes, 1);
});

test('longest sentence carries document positions for jumping', () => {
  const { state } = createTestEditor('', paragraphs('Kurz. Dieser Satz ist deutlich länger.'));
  const { longestSentence } = computeNoteStats(state.doc);
  assert.equal(longestSentence.words, 5);
  assert.equal(state.doc.textBetween(longestSentence.from, longestSentence.to), 'Dieser Satz ist deutlich länger.');
});

test('vocabulary diversity ignores case and numbers', () => {
  const { state } = createTestEditor('', paragraphs('Haus haus HAUS Baum 2024'));
  const stats = computeNoteStats(state.doc);
  assert.equal(stats.uniqueWords, 2);
  assert.equal(stats.lexicalDiversity, 0.5);
});

test('selection range restricts the statistics', () => {
  const { state } = createTestEditor('eins zwei drei vier');
  const stats = computeNoteStats(state.doc, { from: 1, to: 10 });
  assert.equal(stats.words, 2);
  assert.equal(stats.selection, true);
});

test('readability only appears with enough text', () => {
  const { state: short } = createTestEditor('Ein kurzer Satz.');
  assert.equal(computeNoteStats(short.doc).readability, null);
  const long = Array.from({ length: 10 }, () => 'Der Hund läuft schnell nach Hause.').join(' ');
  const { state } = createTestEditor(long);
  const stats = computeNoteStats(state.doc);
  assert.ok(stats.readability >= 70, `score ${stats.readability}`);
  assert.equal(stats.readabilityBand.key, 'easy');
});

test('syllables and Flesch-Amstad formula', () => {
  assert.equal(countSyllables('Haus'), 1);
  assert.equal(countSyllables('Lesbarkeit'), 3);
  assert.equal(countSyllables('Bienenstock'), 3);
  assert.equal(fleschAmstad(10, 1, 15), Math.round(180 - 10 - 58.5 * 1.5));
  assert.equal(fleschAmstad(0, 0, 0), null);
  assert.equal(readabilityBand(25).key, 'very-hard');
});
