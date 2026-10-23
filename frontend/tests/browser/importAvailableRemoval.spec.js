import { expect, test } from '@playwright/test';
import { mount } from './fixtures/importHarness.js';

async function setup(page) {
  const deleted = [];
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (request.method() === 'DELETE' && path.startsWith('/api/import/source/')) deleted.push(path.split('/').at(-1));
  });
  await mount(page, { documents: 0, parkedPages: 3, notifications: true });
  await page.route('**/api/import/source/*', route => {
    if (route.request().method() !== 'DELETE') return route.fallback();
    return route.fulfill({ status: 204 });
  });
  await page.evaluate(() => {
    const draft = window.importFixture.store.availableDraft, sourceId = draft.documents[0].pages[0].sourceFileId;
    draft.files = [[sourceId, new File(['saved-pdf'], 'Gesicherter Scan.pdf', { type: 'application/pdf' })]];
    draft.sourceMeta = [[sourceId, { pageCount: 3, originalName: 'Gesicherter Scan.pdf', sourceType: 'scanner' }]];
    draft.documents[0].meta.form.note = 'Meine erhaltene Notiz';
    draft.documents[0].pages[0].rotation = 90;
  });
  await expect.poll(() => page.evaluate(async () => {
    const draft = await (await import('/src/utils/importDraftStorage.js')).importDraftStorage('import-browser-test');
    return draft?.availableDraft?.files[0]?.[1]?.name;
  })).toBe('Gesicherter Scan.pdf');
  await page.clock.install();
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 1000));
  return deleted;
}

const remove = page => page.getByRole('button', { name: '3 verfügbare Seiten entfernen', exact: true });
async function advanceDraftRevision(page) {
  await page.evaluate(async () => {
    // Simulate another tab updating the serialized record without rewriting
    // hydrated native Files directly into WebKit's IndexedDB.
    const db = await new Promise(resolve => { const request = indexedDB.open('papermind-import-drafts', 2); request.onsuccess = () => resolve(request.result); });
    await new Promise((resolve, reject) => {
      const tx = db.transaction('drafts', 'readwrite'), drafts = tx.objectStore('drafts');
      const request = drafts.get('import-browser-test');
      request.onsuccess = () => drafts.put({ ...request.result, revision: request.result.revision + 1 }, 'import-browser-test');
      tx.oncomplete = resolve; tx.onerror = reject;
    });
    db.close();
  });
}
async function expire(page) {
  const remaining = await page.evaluate(() => window.importFixture.store.availableRemovals[0].expiresAt - Date.now());
  await page.clock.runFor(Math.max(0, remaining));
}

test('removing a saved import opens no pages and undo restores metadata, edits and its PDF', async ({ page }) => {
  const deleted = await setup(page);
  await expect(remove(page)).toHaveAttribute('title', '3 verfügbare Seiten entfernen');
  await remove(page).click();
  await expect(page.locator('.isd-dropzone__available-pages')).toHaveCount(0);
  await expect(page.locator('.isd-page-card')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toBeVisible();
  await page.clock.runFor(9000);
  expect(deleted).toEqual([]);
  await page.getByRole('button', { name: 'Rückgängig', exact: true }).click();
  await page.clock.runFor(1000);
  await expect(page.getByRole('button', { name: '3 verfügbare Seiten öffnen', exact: true })).toBeVisible();
  expect(await page.evaluate(async () => {
    const draft = window.importFixture.store.availableDraft;
    return { note: draft.documents[0].meta.form.note, rotation: draft.documents[0].pages[0].rotation, file: await draft.files[0][1].text() };
  })).toEqual({ note: 'Meine erhaltene Notiz', rotation: 90, file: 'saved-pdf' });
  expect(deleted).toEqual([]);
});

test('only the removed snapshot is discarded after ten seconds, preserving newer available pages', async ({ page }) => {
  const deleted = await setup(page);
  await remove(page).click();
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toBeVisible();
  await page.evaluate(() => {
    const store = window.importFixture.store;
    store.addDocumentFromSource({ sourceFileId: 'new-source', title: 'Neuer Scan', pageCount: 1 });
    store.setStagingFile('new-source', null, { pageCount: 1, sourceType: 'scanner' });
    store.parkDraft();
  });
  const remaining = await page.evaluate(() => window.importFixture.store.availableRemovals[0].expiresAt - Date.now());
  await page.clock.runFor(remaining - 1);
  expect(deleted).toEqual([]);
  await page.clock.runFor(1);
  await expect.poll(() => deleted).toEqual(['saved-layout-source']);
  await page.clock.runFor(300); // Finish the notification's standard leave transition.
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '1 verfügbare Seite öffnen', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.importFixture.store.availableDraft.documents[0].title)).toBe('Neuer Scan');
});

test('undo merges the removed pages with a newer saved draft instead of overwriting either', async ({ page }) => {
  const deleted = await setup(page);
  await remove(page).click();
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toBeVisible();
  await page.evaluate(() => {
    const store = window.importFixture.store;
    store.addDocumentFromSource({ sourceFileId: 'new-source', title: 'Neuer Scan', pageCount: 1 });
    store.setStagingFile('new-source', null, { pageCount: 1, sourceType: 'scanner' });
    store.parkDraft();
  });
  await page.clock.runFor(400);
  await page.getByRole('button', { name: 'Rückgängig', exact: true }).click();
  await page.clock.runFor(11000);
  await expect(page.getByRole('button', { name: '4 verfügbare Seiten öffnen', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.importFixture.store.availableDraft.documents.map(doc => doc.title))).toEqual(['Verfügbare Seiten', 'Neuer Scan']);
  expect(deleted).toEqual([]);
});

test('a reload retains the undo deadline and the full locally stored PDF', async ({ page }) => {
  const deleted = await setup(page);
  await remove(page).click();
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toBeVisible();
  await mount(page, { restore: true, documents: 0, notifications: true });
  await page.clock.runFor(400);
  await expect(page.locator('.isd-dropzone__available-pages')).toHaveCount(0);
  await page.getByRole('button', { name: 'Rückgängig', exact: true }).click();
  await page.clock.runFor(11000);
  await expect(page.getByRole('button', { name: '3 verfügbare Seiten öffnen', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.importFixture.store.availableDraft.files[0][1].name)).toBe('Gesicherter Scan.pdf');
  expect(deleted).toEqual([]);
});

test('a failed final deletion returns the saved pages instead of losing them', async ({ page }) => {
  await setup(page);
  await page.route('**/api/import/source/*', route => route.request().method() === 'DELETE'
    ? route.fulfill({ status: 503, json: { error: { message: 'Nicht erreichbar' } } }) : route.fallback());
  await remove(page).click();
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toBeVisible();
  await expire(page);
  await expect(page.getByRole('button', { name: '3 verfügbare Seiten öffnen', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.importFixture.store.availableDraft.files[0][1].name)).toBe('Gesicherter Scan.pdf');
  await expect(page.getByText('Einige Seiten konnten nicht entfernt werden. Sie stehen wieder unter „Verfügbare Seiten“ bereit.', { exact: true })).toBeVisible();
});

test('the original deadline survives a reload and closing the dialog does not delete early', async ({ page }) => {
  const deleted = await setup(page);
  await remove(page).click();
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toBeVisible();
  const deadline = await page.evaluate(() => window.importFixture.store.availableRemovals[0].expiresAt);
  await page.clock.runFor(4000);
  await mount(page, { restore: true, documents: 0, notifications: true });
  await page.clock.runFor(400);
  expect(await page.evaluate(() => window.importFixture.store.availableRemovals[0].expiresAt)).toBe(deadline);
  await page.getByRole('button', { name: 'Dialog schließen', exact: true }).click();
  await page.clock.runFor(400);
  const remaining = deadline - await page.evaluate(() => Date.now());
  await page.clock.runFor(remaining - 1);
  expect(deleted).toEqual([]);
  await page.clock.runFor(1);
  await expect.poll(() => deleted).toEqual(['saved-layout-source']);
});

test('a conflicting durable draft prevents deletion and keeps the saved pages accessible', async ({ page }) => {
  const deleted = await setup(page);
  await advanceDraftRevision(page);
  await remove(page).click();
  await expect(page.getByRole('button', { name: '3 verfügbare Seiten öffnen', exact: true })).toBeVisible();
  await expect(remove(page)).toBeDisabled();
  await page.clock.runFor(11000);
  expect(deleted).toEqual([]);
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toHaveCount(0);
});

test('a conflicting write during the undo period prevents the final server deletion', async ({ page }) => {
  const deleted = await setup(page);
  await remove(page).click();
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toBeVisible();
  await page.clock.runFor(400);
  await advanceDraftRevision(page);
  await expire(page);
  await expect(page.getByRole('button', { name: '3 verfügbare Seiten öffnen', exact: true })).toBeVisible();
  await expect(remove(page)).toBeDisabled();
  expect(deleted).toEqual([]);
});

test('undo remains visible with a full notification stack and cannot outlive deletion while hovered', async ({ page }) => {
  const deleted = await setup(page);
  await page.evaluate(() => {
    const { notify } = window.importFixture.notifications;
    notify({ type: 'warning', message: 'Vorhandene Meldung eins', timeoutMs: 60000 });
    notify({ type: 'warning', message: 'Vorhandene Meldung zwei', timeoutMs: 60000 });
  });
  await expect(page.getByText('Vorhandene Meldung zwei', { exact: true })).toBeVisible();
  await remove(page).click();
  const undo = page.getByRole('button', { name: 'Rückgängig', exact: true });
  await expect(undo).toBeVisible();
  await page.clock.runFor(400);
  await undo.hover();
  await expire(page);
  await expect.poll(() => deleted).toEqual(['saved-layout-source']);
  await page.clock.runFor(300);
  await expect(undo).toHaveCount(0);
  await expect(page.getByText('Vorhandene Meldung zwei', { exact: true })).toBeVisible();
});

test('a source reused by an active import is protected when removal expires', async ({ page }) => {
  const deleted = await setup(page);
  await remove(page).click();
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toBeVisible();
  await page.evaluate(() => window.importFixture.store.addDocumentFromSource({ sourceFileId: 'saved-layout-source', title: 'Aktiver Import', pageCount: 1 }));
  await expire(page);
  await expect.poll(() => page.evaluate(() => window.importFixture.store.availableRemovals.length)).toBe(0);
  expect(deleted).toEqual([]);
  expect(await page.evaluate(() => window.importFixture.store.documents.map(doc => doc.title))).toEqual(['Aktiver Import']);
});

test('logout cancels pending destructive work instead of using another account', async ({ page }) => {
  const deleted = await setup(page);
  await remove(page).click();
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toBeVisible();
  await page.evaluate(async () => (await import('/src/api/session.js')).resetApiSession('other-account'));
  await page.clock.runFor(11000);
  expect(deleted).toEqual([]);
  await expect(page.getByRole('button', { name: 'Rückgängig', exact: true })).toHaveCount(0);
});

test('pages with an unresolved import submission cannot be removed', async ({ page }) => {
  const deleted = await setup(page);
  await page.evaluate(() => { window.importFixture.store.availableDraft.pendingCommit = { body: { request_id: 'unresolved' }, submitted: {} }; });
  await expect(page.locator('.isd-dropzone__available-pages')).toHaveCount(0);
  expect(deleted).toEqual([]);
});
