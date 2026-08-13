import test from 'node:test';
import assert from 'node:assert/strict';

import { dossierDocumentCardTitle, dossierDocumentPageLabel } from '../src/utils/dossierCards.js';

test('document card separates the redundant PDF suffix from its display title', () => {
  assert.deepEqual(dossierDocumentCardTitle({ title: 'Quittung Hauptuntersuchung.pdf' }), {
    display: 'Quittung Hauptuntersuchung',
    full: 'Quittung Hauptuntersuchung.pdf',
  });
});

test('document card formats singular and plural page labels', () => {
  assert.equal(dossierDocumentPageLabel({ page_count: 1 }), '1 Seite');
  assert.equal(dossierDocumentPageLabel({ page_count: 3 }), '3 Seiten');
});
