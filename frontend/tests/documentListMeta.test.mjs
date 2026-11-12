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

test('document card prefers the canonical correspondent short name', () => {
  const name = resolveDocumentCorrespondent(
    { correspondent_id: 'corr-1', correspondent_name: 'Versorgungsanstalt des Bundes und der Länder' },
    () => ({
      id: 'corr-1',
      name: 'Versorgungsanstalt des Bundes und der Länder',
      short_name: 'VBL',
    })
  );

  assert.equal(name, 'VBL');
});

test('document responses provide the short name before the correspondent directory loads', () => {
  assert.equal(resolveDocumentCorrespondent({
    correspondent_name: 'Kieler Männer-Turnverein',
    correspondent_short_name: 'KMTV',
  }), 'KMTV');
});

test('a cleared short name in the directory takes precedence over a cached document label', () => {
  assert.equal(resolveDocumentCorrespondent({
    correspondent_id: 'club',
    correspondent_name: 'Kieler Männer-Turnverein',
    correspondent_short_name: 'KMTV',
  }, () => ({ short_name: null })), 'Kieler Männer-Turnverein');
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

test('resolveDocumentCorrespondent prefixes the organization of a person', () => {
  const records = {
    o1: { id: 'o1', name: 'Autohaus Müller', kind: 'organization' },
    p1: { id: 'p1', name: 'Torge Quitsch', kind: 'person', parent_id: 'o1' },
  };
  const find = (id) => records[id] || null;
  assert.equal(resolveDocumentCorrespondent({ correspondent_id: 'p1', correspondent_name: 'Torge Quitsch' }, find), 'Autohaus Müller · Torge Quitsch');
  assert.equal(resolveDocumentCorrespondent({ correspondent_id: 'o1', correspondent_name: 'Autohaus Müller' }, find), 'Autohaus Müller');
});
