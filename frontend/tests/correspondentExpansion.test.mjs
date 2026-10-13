import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadGroupExpansion, saveGroupExpansion } from '../src/workspaces/documents/groupExpansion.js';

const groupId = '30000000-0000-4000-8000-000000000001';
function memoryStorage() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
}

test('restores open groups and persists closing all groups', () => {
  const storage = memoryStorage();
  assert.deepEqual([...loadGroupExpansion('alice', storage)], []);
  saveGroupExpansion('alice', new Set([groupId, 'unassigned']), storage);
  assert.deepEqual([...loadGroupExpansion('alice', storage)], [groupId, 'unassigned']);
  saveGroupExpansion('alice', new Set(), storage);
  assert.deepEqual([...loadGroupExpansion('alice', storage)], []);
});

test('keeps expansion preferences separate for each signed-in account', () => {
  const storage = memoryStorage();
  saveGroupExpansion('alice', new Set([groupId]), storage);
  saveGroupExpansion('bob', new Set(['unassigned']), storage);
  saveGroupExpansion('', new Set([groupId]), storage);
  assert.deepEqual([...loadGroupExpansion('alice', storage)], [groupId]);
  assert.deepEqual([...loadGroupExpansion('bob', storage)], ['unassigned']);
  assert.deepEqual([...loadGroupExpansion('', storage)], []);
});

test('ignores malformed storage and invalid keys', () => {
  for (const saved of ['{broken', '{}', 'null', '42']) {
    assert.deepEqual([...loadGroupExpansion('alice', { getItem: () => saved })], []);
  }
  const storage = { getItem: () => JSON.stringify([groupId, groupId, 'unassigned', null, 12, 'unknown']) };
  assert.deepEqual([...loadGroupExpansion('alice', storage)], [groupId, 'unassigned']);
});

test('unavailable browser storage does not prevent opening or closing groups', () => {
  const blocked = {
    getItem() { throw new Error('Storage blocked'); },
    setItem() { throw new Error('Storage blocked'); },
  };
  assert.deepEqual([...loadGroupExpansion('alice', blocked)], []);
  assert.doesNotThrow(() => saveGroupExpansion('alice', new Set([groupId]), blocked));
});

test('document types remember their own groups independently of correspondents and accounts', () => {
  const storage = memoryStorage();
  saveGroupExpansion('alice', new Set([groupId, 'unassigned']), storage);
  saveGroupExpansion('alice', new Set(['type:rechnung', 'unassigned', groupId]), storage, 'document_types');
  assert.deepEqual([...loadGroupExpansion('alice', storage, 'document_types')], ['type:rechnung', 'unassigned']);
  assert.deepEqual([...loadGroupExpansion('alice', storage)], [groupId, 'unassigned']);
  assert.deepEqual([...loadGroupExpansion('bob', storage, 'document_types')], []);
  saveGroupExpansion('alice', new Set(), storage, 'document_types');
  assert.deepEqual([...loadGroupExpansion('alice', storage, 'document_types')], []);
  assert.deepEqual([...loadGroupExpansion('alice', storage)], [groupId, 'unassigned']);
});
