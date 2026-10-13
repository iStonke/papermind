import assert from 'node:assert/strict';
import test from 'node:test';
import { createPinia, setActivePinia } from 'pinia';
import { useCorrespondentStore } from '../src/stores/correspondents.js';
import { useCategoryStore } from '../src/stores/categories.js';
import { reconcileRecordReload } from '../src/utils/recordReload.js';

const json = payload => new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } });

test('a reload preserves new/deleted records but still loads untouched rows', () => {
  const current = [{ id: 'edited', name: 'Neu' }, { id: 'created', name: 'Angelegt' }];
  const incoming = [{ id: 'edited', name: 'Alt' }, { id: 'deleted', name: 'Gelöscht' }, { id: 'untouched', name: 'Unverändert' }];
  const versions = new Map([['edited', 2], ['created', 3], ['deleted', 4]]);
  assert.deepEqual(reconcileRecordReload(current, incoming, versions, 1), [current[0], incoming[2], current[1]]);
});

test('a stale list response cannot overwrite an acknowledged correspondent edit', async () => {
  setActivePinia(createPinia());
  const store = useCorrespondentStore();
  store.correspondents = [{ id: 'a', name: 'Alt', aliases: [], usage_count: 12 }];
  let releaseList;
  const previousFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push(options.method || 'GET');
    if (options.method === 'PATCH') return json({ id: 'a', name: 'Neu', aliases: [], usage_count: null });
    return new Promise(resolve => releaseList = () => resolve(json({ items: [{ id: 'a', name: 'Alt', aliases: [], usage_count: 12 }] })));
  };
  try {
    const loading = store.fetchCorrespondents();
    await store.updateCorrespondent('a', { name: 'Neu' }, { silent: true });
    assert.equal(store.findById('a').name, 'Neu');
    assert.equal(store.findById('a').usage_count, 12);
    releaseList();
    await loading;
    assert.equal(store.findById('a').name, 'Neu');
    assert.deepEqual(calls, ['GET', 'PATCH']);
  } finally { globalThis.fetch = previousFetch; }
});

test('alias acknowledgements preserve name edits and document counts', async () => {
  setActivePinia(createPinia());
  const store = useCorrespondentStore();
  store.correspondents = [{ id: 'a', name: 'Neu', aliases: [], usage_count: 7 }];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => json({ id: 'a', name: 'Alt', usage_count: null, aliases: [{ id: 'alias', alias: 'Erkannt' }] });
  try {
    await store.addAlias('a', 'Erkannt');
    assert.equal(store.findById('a').name, 'Neu');
    assert.equal(store.findById('a').usage_count, 7);
    assert.equal(store.findById('a').aliases[0].alias, 'Erkannt');
  } finally { globalThis.fetch = previousFetch; }
});

test('document type updates use the acknowledgement and ignore an older reload', async () => {
  setActivePinia(createPinia());
  const store = useCategoryStore();
  store.categories = [{ id: 'a', name: 'Rechnung', usage_count: 4 }];
  const previousFetch = globalThis.fetch;
  let releaseList;
  globalThis.fetch = async (url, options) => {
    if (options.method === 'PATCH') return json({ id: 'a', name: 'Beleg', usage_count: null });
    return new Promise(resolve => releaseList = () => resolve(json({ items: [{ id: 'a', name: 'Rechnung', usage_count: 4 }] })));
  };
  try {
    const loading = store.fetchCategories();
    await store.updateCategory('a', { name: 'Beleg' }, { silent: true });
    releaseList();
    await loading;
    assert.equal(store.findById('a').name, 'Beleg');
    assert.equal(store.findById('a').usage_count, 4);
  } finally { globalThis.fetch = previousFetch; }
});
