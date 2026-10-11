import { expect, test } from '@playwright/test';

test('IndexedDB drafts stay with their account and legacy drafts require server ownership', async ({ page }) => {
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    if (path.startsWith('/api/auth/')) return route.fulfill({ status: 401, json: {} });
    if (path === '/api/notes/legacy-a' && route.request().headers().authorization === 'Bearer account-a') {
      return route.fulfill({ json: { id: 'legacy-a' } });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('/login');
  await expect(page.getByLabel('Benutzername oder E-Mail')).toBeVisible();
  const result = await page.evaluate(async () => {
    // Seed the previous schema before the new module opens version 2.
    await new Promise((resolve, reject) => {
      const request = indexedDB.open('papermind-local-drafts', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('note-drafts', { keyPath: 'noteId' });
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const db = request.result;
        const transaction = db.transaction('note-drafts', 'readwrite');
        transaction.objectStore('note-drafts').put({ noteId: 'legacy-a', title: 'Legacy private A',
          bodyJson: { type: 'doc', content: [] }, baseRevision: 1, clientVersion: 'legacy-v1', savedAt: Date.now() });
        transaction.oncomplete = () => { db.close(); resolve(); };
      };
    });
    const session = await import('/src/api/session.js');
    // Vite HMR appends a revision to live modules. Reuse the app's module so
    // the test writes the same in-memory token that the draft API reads.
    const clientUrl = performance.getEntriesByType('resource').find(entry =>
      new URL(entry.name).pathname === '/src/api/client.js').name;
    const { setToken } = await import(clientUrl);
    const drafts = await import('/src/utils/noteDraftStorage.js');
    const activate = owner => { session.resetApiSession(owner); setToken(owner); };
    const draft = title => ({ noteId: 'same-note-id', title, bodyJson: { type: 'doc', content: [] },
      baseRevision: 1, clientVersion: title, savedAt: Date.now() });
    activate('account-a');
    await drafts.putNoteDraft(draft('Private A'));
    const migrated = await drafts.getNoteDraft('legacy-a');
    activate('account-b');
    const foreignDraft = await drafts.getNoteDraft('same-note-id');
    const foreignLegacy = await drafts.getNoteDraft('legacy-a');
    await drafts.putNoteDraft(draft('Private B'));
    const ownB = await drafts.getNoteDraft('same-note-id');
    await drafts.deleteNoteDraft('same-note-id');
    activate('account-a');
    const ownA = await drafts.getNoteDraft('same-note-id');
    return { migrated: migrated?.title, foreignDraft, foreignLegacy, ownB: ownB?.title, ownA: ownA?.title };
  });
  expect(result).toEqual({ migrated: 'Legacy private A', foreignDraft: null, foreignLegacy: null,
    ownB: 'Private B', ownA: 'Private A' });
});
