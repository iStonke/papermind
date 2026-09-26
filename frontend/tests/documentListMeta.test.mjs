import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveDocumentCorrespondent } from '../src/workspaces/documents/documentListMeta.js';

test('document card keeps the correspondent name delivered by the list API', () => {
  const name = resolveDocumentCorrespondent(
    { correspondent_id: 'corr-1', correspondent_name: 'Versorgungsanstalt des Bundes und der Länder' },
    () => ({ id: 'corr-1', name: 'VBL' })
  );

  assert.equal(name, 'Versorgungsanstalt des Bundes und der Länder');
});

test('document card resolves a stored correspondent id when a cached list item has no name', () => {
  const correspondents = new Map([
    ['corr-vbl', { id: 'corr-vbl', name: 'VBL' }],
  ]);

  const name = resolveDocumentCorrespondent(
    { correspondent_id: 'corr-vbl', correspondent_name: null },
    (id) => correspondents.get(id) || null
  );

  assert.equal(name, 'VBL');
});

test('document card remains empty when no correspondent is assigned', () => {
  assert.equal(resolveDocumentCorrespondent({}, () => null), '');
});
