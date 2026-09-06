import { readNoteEditorSource } from './helpers/noteEditorSource.mjs';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const editorSource = await readNoteEditorSource();

// Der onUpdate-Block: von `onUpdate:` bis zum nächsten Handler `onSelectionUpdate:`.
const onUpdate = editorSource.match(/onUpdate:\s*\(\{ editor: ed \}\) => \{([\s\S]*?)\n {2}\},\n {2}onSelectionUpdate:/)?.[1] || '';

test('onUpdate serialises the document only once per keystroke', () => {
  assert.notEqual(onUpdate, '', 'onUpdate-Block nicht gefunden');
  // Genau ein getJSON() und ein getText() im heißen Pfad (vorher: je zweimal).
  assert.equal((onUpdate.match(/ed\.getJSON\(\)/g) || []).length, 1);
  assert.equal((onUpdate.match(/ed\.getText\(\)/g) || []).length, 1);
  // Das eine JSON wird für beide Emits wiederverwendet und als Referenz gemerkt.
  assert.match(onUpdate, /const json = ed\.getJSON\(\)/);
  assert.match(onUpdate, /const text = ed\.getText\(\)/);
  assert.match(onUpdate, /lastEmittedModelValue = json/);
  assert.match(onUpdate, /emit\('update:modelValue', json\)/);
  assert.match(onUpdate, /emit\('change', \{ json, text, words: words\.value \}\)/);
  assert.match(onUpdate, /updateWordCount\(ed, text\)/);
});

test('modelValue watcher short-circuits self-originated changes by reference before serialising', () => {
  // Der billige Referenzvergleich muss VOR dem teuren JSON.stringify-Vergleich stehen.
  const refIdx = editorSource.indexOf('if (toRaw(next) === lastEmittedModelValue) return;');
  const stringifyIdx = editorSource.indexOf('const current = JSON.stringify(ed.getJSON());');
  assert.ok(refIdx > 0, 'Referenz-Kurzschluss fehlt');
  assert.ok(stringifyIdx > 0, 'Struktur-Vergleich fehlt');
  assert.ok(refIdx < stringifyIdx, 'Referenzvergleich muss vor der Serialisierung stehen');
});
