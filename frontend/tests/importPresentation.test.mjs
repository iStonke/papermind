import assert from 'node:assert/strict';
import test from 'node:test';
import { effectScope, nextTick, ref } from 'vue';
import { usefulAnalysisNote, importAnalysisScope } from '../src/utils/importPresentation.js';
import { useImportFieldFocus } from '../src/composables/useImportFieldFocus.js';

test('automatic notes discard metadata repetition and broken OCR, preserving substantive summaries', () => {
  for (const note of ['Absender: %; é&‘. Dokumenttyp: Verträge', 'Dokumenttyp: Brief', '%%%% &&&& ???', 'Kündigung', '']) {
    assert.equal(usefulAnalysisNote(note, { title:'Kündigung' }), '');
  }
  const summary = 'Deine Mitgliedschaft endet am 30. Juni 2026.';
  assert.equal(usefulAnalysisNote(summary, { document_type:'Kündigung' }), summary);
  assert.equal(usefulAnalysisNote('Absender: Dr. R. Müller', { sender_raw:'Dr. R. Müller' }), '');
  assert.equal(usefulAnalysisNote('Absender: Firma. Bitte den Beleg bis Freitag einreichen.', null), 'Absender: Firma. Bitte den Beleg bis Freitag einreichen.');
});
test('analysis scope only reports measured page coverage and maps the analyzed source pages', () => {
  const pages = Array.from({ length:7 }, (_, pageIndex) => ({ sourceFileId:'scan', pageIndex }));
  assert.equal(importAnalysisScope({}, pages), '');
  assert.match(importAnalysisScope({ pages_analyzed:5, pages_total:7, page_refs:pages.slice(0, 5).map(page => `scan:${page.pageIndex}`) }, pages), /Seiten 1, 2, 3, 4, 5 \(5 von 7\).*nicht berücksichtigt/);
  assert.doesNotMatch(importAnalysisScope({ pages_analyzed:7, pages_total:7 }, pages), /nicht berücksichtigt/);
});
test('focused fields defer the latest result until blur, and closing drops deferred changes', async () => {
  const scope = effectScope();
  const document = ref({ id:'first' });
  const focus = scope.run(() => useImportFieldFocus(document));
  let applied = '';
  focus.focus('name');
  assert.equal(focus.defer('first', 'title', () => { applied = 'old'; }), true);
  focus.defer('first', 'title', () => { applied = 'latest'; });
  assert.equal(applied, '');
  assert.equal(focus.defer('first', 'date', () => {}), false);
  focus.blur('name');
  assert.equal(applied, 'latest');
  focus.focus('date');
  focus.defer('first', 'date', () => { applied = 'other-document'; });
  document.value = { id:'second' };
  await nextTick();
  assert.equal(applied, 'other-document');
  assert.equal(focus.defer('second', 'date', () => { applied = 'discarded'; }), true);
  focus.reset();
  focus.blur('date');
  assert.equal(applied, 'other-document');
  scope.stop();
});
