import test from 'node:test';
import assert from 'node:assert/strict';
import { knowledgeDraft, knowledgePatch, missingDocumentFields, resolveDocumentKnowledge } from '../src/utils/documentKnowledge.js';

test('knowledge prefers document corrections and retains the original AI evidence', () => {
  const result = resolveDocumentKnowledge({ ai_status: 'done', document_type: 'Manuell geändert', ai_document_type: 'Rechnung',
    ai_document_date: '2026-10-30', ai_sender: 'KMTV', ai_recipient: 'Jan', ai_amount: 0, ai_currency: 'EUR',
    ai_summary: 'Kurze Zusammenfassung.', ai_processed_at: '2026-10-30T10:00:00Z', ai_suggested_tags: ['Sport', ' Sport ', '  ', null] });
  assert.equal(result.status, 'Abgeschlossen');
  assert.equal(result.fields.find(field => field.label === 'Dokumenttyp').value, 'Manuell geändert');
  assert.equal(result.fields.find(field => field.label === 'Dokumentdatum').value, '30.10.2026');
  assert.match(result.fields.find(field => field.label === 'Betrag').value, /^0,00.*€$/);
  assert.equal(result.summary, 'Kurze Zusammenfassung.');
  assert.deepEqual(result.tags, ['Sport']);
  assert.match(result.processed, /30\.10\.2026/);
});

test('compact information includes zero amounts and parties; manual clears suppress AI fallback', () => {
  const document = { ai_document_type: 'Rechnung', ai_amount: 12, ai_currency: 'USD', ai_recipient: 'Alt', ai_sender: 'Absender',
    amount: 0, currency: 'EUR', recipient: 'Neu', correspondent_id: 'sender', correspondent_name: 'Korrigiert' };
  const result = resolveDocumentKnowledge(document);
  assert.match(result.compactPrimary, /^0,00.*€ · Rechnung$/);
  assert.equal(result.compactParties, 'Korrigiert → Neu');
  const cleared = resolveDocumentKnowledge({ ...document, amount: null, recipient: null, correspondent_id: null,
    flags: { manual_metadata_fields: ['amount', 'recipient', 'correspondent_id', 'document_type'] } });
  assert.equal(cleared.compactPrimary, '');
  assert.equal(cleared.compactParties, '');
  assert.equal(document.ai_recipient, 'Alt');
});

test('editing patches only changed fields and accepts decimal comma without losing zero or negatives', () => {
  const initial = knowledgeDraft({ ai_amount: 12.5, ai_currency: 'EUR', ai_recipient: 'Max', ai_document_type: 'Rechnung' });
  assert.deepEqual(knowledgePatch(initial, initial), {});
  assert.deepEqual(knowledgePatch({ ...initial, amount: '0', recipient: '' }, initial), { amount: 0, recipient: null });
  assert.deepEqual(knowledgePatch({ ...initial, amount: '-225,99', currency: 'usd' }, initial), { amount: -225.99, currency: 'USD' });
  for (const amount of ['1.234,56', '12,345', 'NaN', 'Infinity', '10000000000']) {
    assert.throws(() => knowledgePatch({ ...initial, amount }, initial), /Betrag/);
  }
  assert.throws(() => knowledgePatch({ ...initial, currency: 'Euro' }, initial), /Währung/);
});

test('empty, pending and invalid results do not invent an analysis or currency', () => {
  const result = resolveDocumentKnowledge({ ai_amount: NaN, ai_summary: ' ', ai_document_date: 'kaputt', ai_status: 'pending', ai_processed_at: 'invalid' });
  assert.equal(result.hasResults, false);
  assert.equal(result.status, 'Noch nicht ausgewertet');
  assert.equal(result.fields.length, 0);
  assert.equal(result.processed, '');
  const noCurrency = resolveDocumentKnowledge({ ai_amount: 12.5 });
  assert.equal(noCurrency.fields.find(field => field.label === 'Betrag').value, '12,50');
  assert.equal(noCurrency.status, 'Ergebnisse vorhanden');
});

test('failed or running analyses keep existing results clearly marked and do not expose internal errors', () => {
  const document = { ai_status: 'error', ai_summary: 'Vorheriges Ergebnis', flags: { ai_classification: { error: 'Interne Serveradresse' } } };
  const failed = resolveDocumentKnowledge(document);
  assert.equal(failed.status, 'Fehlgeschlagen');
  assert.match(failed.message, /zuletzt verfügbaren Ergebnisse/);
  assert.equal(failed.processedLabel, 'Letzter Versuch');
  assert.doesNotMatch(JSON.stringify(failed), /Interne Serveradresse/);
  const running = resolveDocumentKnowledge(document, { busy: true });
  assert.equal(running.status, 'Wird ausgewertet');
  assert.equal(running.summary, document.ai_summary);
  assert.match(running.message, /Bis zum Abschluss/);
  assert.equal(resolveDocumentKnowledge({ ai_status: 'skipped' }).status, 'Übersprungen');
});

test('open fields follow the current editable values and never include the optional notes', () => {
  const complete = { display_name: 'Rechnung', document_date: '2026-10-30', category: 'Rechnung', correspondent_id: 'sender', tags: ['Sport'] };
  assert.deepEqual(missingDocumentFields(complete), []);
  assert.deepEqual(missingDocumentFields({ ...complete, document_date: '', tags: [] }), ['Dokumentdatum', 'Tags']);
  assert.deepEqual(resolveDocumentKnowledge({}, { missingFields: [] }).missing, []);
  assert.deepEqual(resolveDocumentKnowledge(complete, { missingFields: ['Dokumenttyp'] }).missing, ['Dokumenttyp']);
});

test('completeness counts only the five document fields, independently of AI recognition', () => {
  const empty = resolveDocumentKnowledge({ ai_status: 'done', ai_document_type: 'Rechnung', ai_summary: 'Erkannte Angaben' });
  assert.equal(empty.filledCount, 0);
  assert.equal(empty.completeness.length, 5);
  const complete = resolveDocumentKnowledge({}, { missingFields: [] });
  assert.equal(complete.filledCount, 5);
  const partial = resolveDocumentKnowledge({}, { missingFields: ['Tags', 'Tags', 'Notizen'] });
  assert.equal(partial.filledCount, 4);
  assert.deepEqual(partial.missing, ['Tags']);
  assert.equal(partial.completeness.find(field => field.label === 'Tags').filled, false);
});
