import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDocumentMetadataPatch } from '../src/utils/documentMetadata.js';

const detail = {
  document_date: '2026-06-15',
  notes: 'Bestehende Notiz',
  display_name: 'Bestehender Name'
};

test('buildDocumentMetadataPatch normalisiert ein gültiges deutsches Datum', () => {
  const result = buildDocumentMetadataPatch({
    detail,
    currentNameDraft: 'Bestehender Name',
    draftName: 'Bestehender Name',
    draftDate: '1.2.2024',
    draftNotes: 'Bestehende Notiz'
  });

  assert.deepEqual(result.patchBody, { document_date: '2024-02-01' });
  assert.equal(result.dateChanged, true);
});

test('ein ungültiges Datum blockiert Name und Notizen nicht', () => {
  const result = buildDocumentMetadataPatch({
    detail,
    currentNameDraft: 'Bestehender Name',
    draftName: ' Neuer   Name ',
    draftDate: '31.02.2026',
    draftNotes: 'Neue Notiz'
  });

  assert.equal(result.parsedDocumentDate.ok, false);
  assert.deepEqual(result.patchBody, {
    display_name: 'Neuer Name',
    notes: 'Neue Notiz'
  });
});

test('ein benutzerdefinierter Dokumentname kann entfernt werden', () => {
  const result = buildDocumentMetadataPatch({
    detail,
    currentNameDraft: 'Bestehender Name',
    draftName: '',
    draftDate: '15.06.2026',
    draftNotes: 'Bestehende Notiz'
  });

  assert.deepEqual(result.patchBody, { display_name: null });
});

test('eine geleerte Notiz wird als null übertragen', () => {
  const result = buildDocumentMetadataPatch({
    detail,
    currentNameDraft: 'Bestehender Name',
    draftName: 'Bestehender Name',
    draftDate: '15.06.2026',
    draftNotes: ''
  });

  assert.deepEqual(result.patchBody, { notes: null });
});

test('unveränderte Metadaten erzeugen keinen PATCH-Inhalt', () => {
  const result = buildDocumentMetadataPatch({
    detail,
    currentNameDraft: 'Bestehender Name',
    draftName: 'Bestehender Name',
    draftDate: '15.06.2026',
    draftNotes: 'Bestehende Notiz'
  });

  assert.deepEqual(result.patchBody, {});
  assert.equal(result.hasChanges, false);
});
