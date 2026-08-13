import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../src/views/DossierWorkspace.vue', import.meta.url), 'utf8');

test('note editor follows the compact PaperMind dialog language', () => {
  assert.match(source, /max-width="500"/);
  assert.match(source, /label="Titel"\s+variant="outlined"\s+density="comfortable"/);
  assert.match(source, /label="Notiz"\s+variant="outlined"\s+density="comfortable"/);
  assert.doesNotMatch(source, /card-class="dossier-note-dialog"/);
  assert.doesNotMatch(source, /variant="solo-filled"/);
});

test('selected note color is immediately recognizable and accessible', () => {
  assert.match(source, /role="radiogroup" aria-label="Notizfarbe"/);
  assert.match(source, /role="radio"/);
  assert.match(source, /:aria-checked="noteDraft\.color === option\.value"/);
  assert.match(source, /selectedNoteColorLabel/);
  assert.match(source, /note-editor__swatch--active/);
  assert.match(source, /<v-icon v-if="noteDraft\.color === option\.value" size="15">mdi-check<\/v-icon>/);
  assert.match(source, /0 0 0 2px var\(--pm-accent\)/);
});

test('note colors have human-readable names instead of exposing hex values', () => {
  for (const label of ['Sonnengelb', 'Salbeigrün', 'Himmelblau', 'Lavendel', 'Koralle']) {
    assert.match(source, new RegExp(label));
  }
});
