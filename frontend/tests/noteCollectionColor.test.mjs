import test from 'node:test';
import assert from 'node:assert/strict';
import { noteCollectionColor } from '../src/utils/noteCollectionColor.js';

test('notebooks and notes inherit collection color, ignoring older notebook colors', () => {
  const collections = [{ id: 'work', color: '#2563eb' }, { id: 'home', color: '#0d9488' }];
  const notebook = { collection_id: 'work', color: '#db2777' };
  assert.equal(noteCollectionColor(notebook, collections), '#2563eb');
  assert.equal(noteCollectionColor({ collection_id: 'work', notebook_id: null }, collections), '#2563eb');
  collections[0].color = '#ca8a04';
  assert.equal(noteCollectionColor(notebook, collections), '#ca8a04');
  notebook.collection_id = 'home';
  assert.equal(noteCollectionColor(notebook, collections), '#0d9488');
});
test('missing collection or color uses the neutral fallback rather than a notebook color', () => {
  assert.equal(noteCollectionColor({ collection_id: 'work', color: '#db2777' }, [{ id: 'work', color: null }]), null);
  assert.equal(noteCollectionColor(undefined, []), null);
});
