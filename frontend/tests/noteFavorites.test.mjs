import test from 'node:test';
import assert from 'node:assert/strict';
import { createPinia, setActivePinia } from 'pinia';
import { useNotesStore } from '../src/stores/notes.js';

for (const fail of [false, true]) {
  test(`direct favorites entry ${fail ? 'restores the card after a failed request' : 'removes the card without loading the notes workspace'}`, async (t) => {
    setActivePinia(createPinia());
    const store = useNotesStore();
    const note = { id: 'favorite-only', title: 'Einkauf', preview: 'Äpfel', is_favorite: true };
    store.favoriteNotes = [note];
    assert.equal(store.notes.length, 0);
    t.mock.method(globalThis, 'fetch', async (url, options) => {
      assert.match(String(url), /\/api\/notes\/favorite-only$/);
      assert.equal(options.method, 'PATCH');
      assert.deepEqual(JSON.parse(options.body), { is_favorite: false });
      assert.equal(store.favoriteNotes.length, 0);
      return new Response(JSON.stringify(fail ? { detail: 'Speichern fehlgeschlagen' } : { ...note, is_favorite: false }), {
        status: fail ? 500 : 200, headers: { 'Content-Type': 'application/json' },
      });
    });
    if (fail) {
      await assert.rejects(store.setFavorite(note.id, false));
      assert.equal(store.favoriteNotes.length, 1);
      assert.equal(store.favoriteNotes[0].is_favorite, true);
      assert.equal(store.favoriteNotes[0].preview, 'Äpfel');
    } else {
      await store.setFavorite(note.id, false);
      assert.equal(store.favoriteNotes.length, 0);
    }
  });
}
