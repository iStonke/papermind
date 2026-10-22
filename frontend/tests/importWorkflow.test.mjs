import test from 'node:test';
import assert from 'node:assert/strict';
import { createPinia, setActivePinia } from 'pinia';
import { ref } from 'vue';
import { useImportStagingStore } from '../src/stores/importStaging.js';
import { useImportDocumentForm } from '../src/composables/useImportDocumentForm.js';
import { meaningfulSuggestion, canOfferTitle, documentRevision, ensureImportForm, validateImportDocument, applyFieldProposal, commitSubset } from '../src/utils/importWorkflow.js';
import { scanImageQuality } from '../src/utils/scanImageQuality.js';
import { analysisPending, acceptAnalysisSnapshot, transientAnalysisError } from '../src/utils/importAnalysis.js';

test('progress snapshots cannot regress from newer results to older rules or failures', () => {
  const meta = {};
  const ready = { status: 'ready', meta: { analysis_phase: 'llm', analysis_job_id: 'job', analysis_sequence: 3, analysis_pending: false, analysis_started_at: 20 } };
  assert.equal(acceptAnalysisSnapshot(meta, ready, 'revision'), true);
  assert.equal(acceptAnalysisSnapshot(meta, { status: 'error', meta: { analysis_job_id: 'job', analysis_sequence: 2 } }, 'revision'), false);
  assert.equal(acceptAnalysisSnapshot(meta, { status: 'ready', meta: { analysis_phase: 'rule' } }, 'revision'), false);
  assert.equal(acceptAnalysisSnapshot(meta, { status: 'error', meta: {} }, 'revision'), false);
  assert.equal(acceptAnalysisSnapshot(meta, { status: 'error', meta: { analysis_job_id: 'old-job', analysis_started_at: 10 } }, 'revision'), false);
  assert.equal(acceptAnalysisSnapshot(meta, { status: 'pending_ocr', meta: { analysis_job_id: 'job', analysis_sequence: 3, analysis_pending: true } }, 'revision'), false);
  assert.equal(acceptAnalysisSnapshot(meta, { status: 'ready', meta: { analysis_phase: 'rule', analysis_job_id: 'new-job', analysis_started_at: 30, analysis_sequence: 1, analysis_pending: true } }, 'revision'), true);
  assert.equal(acceptAnalysisSnapshot(meta, { status: 'error', meta: { analysis_job_id: 'job', analysis_started_at: 20, analysis_sequence: 4 } }, 'revision'), false);
  assert.equal(acceptAnalysisSnapshot(meta, { status: 'ready', meta: { analysis_phase: 'rule' } }, 'new-revision'), true);
  assert.equal(analysisPending({ status: 'ready', meta: { refinement_pending: true } }), true);
  assert.equal(analysisPending({ status: 'ready', meta: { refinement_pending: true, analysis_pending: false } }), false);
  assert.equal(transientAnalysisError({ name: 'AbortError' }), true);
  assert.equal(transientAnalysisError({ status: 503 }), true);
  assert.equal(transientAnalysisError({ status: 400 }), false);
});

test('progressive refinement keeps stable values, upgrades provenance and offers real changes', () => {
  const { doc } = fixture();
  const form = ensureImportForm(doc);
  applyFieldProposal(doc, 'date', '15.10.2026', 0, () => form.date, value => { form.date = value; }, 'Regeln');
  applyFieldProposal(doc, 'date', '16.10.2026', 0, () => form.date, value => { form.date = value; }, 'KI');
  assert.equal(form.date, '15.10.2026');
  assert.equal(form.proposals.date.value, '16.10.2026');
  applyFieldProposal(doc, 'date', '15.10.2026', 0, () => form.date, value => { form.date = value; }, 'KI');
  assert.equal(form.aiFilled.date, 'KI');
  assert.equal(form.proposals.date, undefined);
  applyFieldProposal(doc, 'title', 'Kündigung', 0, () => doc.title, value => { doc.title = value; }, 'Regeln');
  applyFieldProposal(doc, 'title', 'TSV Flintbek Kündigung', 0, () => doc.title, value => { doc.title = value; }, 'KI');
  assert.equal(doc.title, 'TSV Flintbek Kündigung');
  assert.equal(form.previousValues.title, 'Arbeitsstätte');
});

function fixture() {
  setActivePinia(createPinia());
  const store = useImportStagingStore();
  const doc = store.addDocumentFromSource({ sourceFileId: 'source', title: 'Arbeitsstätte', pageCount: 3 });
  return { store, doc };
}
test('missing and generic subjects never offer to replace a meaningful name', () => {
  const { doc } = fixture();
  for (const suggestion of [null, '', '  ', 'Ohne Betreff', 'Unbekannt', 'null', 'Sonstiges', '  Arbeitsstätte  ']) {
    doc.meta.titleSuggestion = suggestion;
    assert.equal(canOfferTitle(doc), false, String(suggestion));
  }
  doc.meta.titleSuggestion = 'Zuordnung Arbeitsstätte Kiel';
  assert.equal(canOfferTitle(doc), true);
  doc.meta.dismissedTitle = doc.meta.titleSuggestion;
  assert.equal(canOfferTitle(doc), false);
  assert.equal(meaningfulSuggestion('Ohne Betreff'), '');
});
test('manual clearing and edits during an asynchronous request reject automatic replacement', async () => {
  const { doc } = fixture();
  const form = ensureImportForm(doc);
  const revision = form.revisions.category || 0;
  await Promise.resolve();
  form.category = null;
  form.touched.category = true;
  form.revisions.category = 1;
  assert.equal(applyFieldProposal(doc, 'category', 'Brief', revision, () => form.category, value => { form.category = value; }), false);
  assert.equal(form.category, null);
  assert.equal(form.proposals.category.value, 'Brief');
  form.dismissed.category = 'Brief';
  delete form.proposals.category;
  applyFieldProposal(doc, 'category', 'Brief', revision, () => form.category, value => { form.category = value; });
  assert.equal(form.proposals.category, undefined);
});
test('document selection owns separate fields, manual decisions and provenance', () => {
  const { store, doc } = fixture();
  const second = store.addDocumentFromSource({ sourceFileId: 'other', title: 'Anderes', pageCount: 1 });
  const selected = ref(doc);
  const fields = useImportDocumentForm(selected);
  fields.docDate.value = '1.2.2026';
  fields.docDateTouched.value = true;
  selected.value = second;
  assert.equal(fields.docDate.value, '');
  assert.equal(fields.docDateTouched.value, false);
  fields.docNote.value = 'Zweites Dokument';
  selected.value = doc;
  assert.equal(fields.docDate.value, '1.2.2026');
  assert.equal(fields.docNote.value, '');
  assert.equal(fields.docDateTouched.value, true);
});
test('selection import builds a subset while preserving all original pages and sources', () => {
  const { store, doc } = fixture();
  const selected = new Set([doc.pages[1].id]);
  const result = commitSubset(store.documents, selected);
  assert.equal(result[0].pages.length, 1);
  assert.equal(doc.pages.length, 3);
  store.completePages(result[0].pages.map(page => page.id));
  assert.deepEqual(store.documents[0].pages.map(page => page.pageIndex), [0, 2]);
});
test('acknowledging an old request preserves pages appended during that request', () => {
  const { store, doc } = fixture();
  const sent = doc.pages.map(page => page.id);
  store.appendSourceToDocument(doc.id, { sourceFileId: 'later', pageCount: 1 });
  store.completePages(sent);
  assert.equal(store.documents.length, 1);
  assert.equal(store.documents[0].pages[0].sourceFileId, 'later');
});
test('document revision changes on selection, order, rotation, colour and source replacement', () => {
  const { store, doc } = fixture();
  let previous = documentRevision(doc, store.sourceMetaById);
  for (const mutate of [() => store.rotatePage(doc.pages[0].id), () => store.setAllPagesColorMode('grayscale'),
    () => doc.pages.reverse(), () => store.sourceMetaById.set('source', { sourceRevision: 'new' }), () => doc.pages.pop()]) {
    mutate();
    const next = documentRevision(doc, store.sourceMetaById);
    assert.notEqual(next, previous);
    previous = next;
  }
});
test('every import metadata field except notes is required, including at least one tag', () => {
  const { doc } = fixture();
  const form = ensureImportForm(doc);
  assert.deepEqual(Object.keys(validateImportDocument(doc)), ['date', 'category', 'correspondent', 'tags']);
  Object.assign(form, { date: '1.2.2026', category: 'Brief', correspondentId: 'sender', note: '' });
  doc.meta.pendingTagNames = ['Unterlagen'];
  assert.deepEqual(validateImportDocument(doc), {});
  for (const [field, key] of [['date', 'date'], ['category', 'category'], ['correspondentId', 'correspondent']]) {
    const original = form[field];
    form[field] = '  ';
    assert.ok(validateImportDocument(doc)[key]);
    form[field] = original;
  }
  form.date = '31.2.2026';
  assert.ok(validateImportDocument(doc).date);
  form.date = '1.2.2026';
  doc.meta.pendingTagNames = ['  '];
  assert.ok(validateImportDocument(doc).tags);
  doc.tags = ['existing-tag'];
  assert.deepEqual(validateImportDocument(doc), {});
  doc.title = '  ';
  assert.ok(validateImportDocument(doc).title);
});
test('inline validation ignores empty fields but still reports malformed values', () => {
  const { doc } = fixture();
  const form = ensureImportForm(doc);
  doc.title = '   ';
  form.date = '   ';
  assert.deepEqual(validateImportDocument(doc, { requireComplete: false }), {});
  assert.deepEqual(Object.keys(validateImportDocument(doc)), ['title', 'date', 'category', 'correspondent', 'tags']);
  doc.title = 'A'.repeat(201);
  form.date = '31.2.2026';
  form.note = 'A'.repeat(10001);
  assert.deepEqual(Object.keys(validateImportDocument(doc, { requireComplete: false })), ['title', 'date', 'note']);
  doc.title = '';
  form.date = '';
  form.note = '';
  assert.deepEqual(validateImportDocument(doc, { requireComplete: false }), {});
  assert.ok(validateImportDocument(doc).date);
});
test('removing a page preserves the remaining identities and the source until commit or discard', () => {
  const { store, doc } = fixture();
  store.setStagingFile('source', null, { pageCount: 3 });
  const original = doc.pages.map(page => page.id);
  store.removePage(original[1]);
  assert.deepEqual(store.documents[0].pages.map(page => page.id), [original[0], original[2]]);
  assert.deepEqual(store.documents[0].pages.map(page => page.pageIndex), [0, 2]);
  assert.equal(store.sourceMetaById.has('source'), true);
});
test('a potentially blank page produces a review hint without modifying pixels', () => {
  const data = new Uint8ClampedArray(40 * 40 * 4).fill(255);
  assert.match(scanImageQuality({ data, width: 40, height: 40 }), /Möglicherweise leer/);
  assert.ok(data.every(value => value === 255));
});

test('removing the last page leaves the import empty', () => {
  const { store, doc } = fixture();
  doc.pages = doc.pages.slice(0, 1);
  const pageId = doc.pages[0].id;
  store.removePage(pageId);
  assert.equal(store.documents.length, 0);
  assert.equal(store.totalPages, 0);
});

test('skewed text lines are marked for review', () => {
  const width = 240;
  const data = new Uint8ClampedArray(width * width * 4).fill(255);
  for (const baseline of [50, 90, 130, 170]) for (let x = 20; x < 220; x++) for (let thickness = 0; thickness < 2; thickness++) {
    const y = Math.round(baseline + Math.tan(4 * Math.PI / 180) * x) + thickness;
    const index = (y * width + x) * 4;
    data[index] = data[index + 1] = data[index + 2] = 30;
  }
  assert.match(scanImageQuality({ data, width, height: width }), /schief/);
});
