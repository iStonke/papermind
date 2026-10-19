import { test, expect } from '@playwright/test';

const scanImage = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="280"><rect width="200" height="280" fill="white"/><rect x="20" y="20" width="160" height="35" fill="#137c80"/><text x="20" y="90">Scanvorschau</text></svg>';

async function mount(page) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route(url => url.pathname.startsWith('/api/'), route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/file') || path.includes('/color-preview')) return route.fulfill({ status: 404 });
    if (path.endsWith('/suggest-title')) return route.fulfill({ json: { status: 'ready', suggestion: '', meta: {} } });
    return route.fulfill({ json: { items: [] } });
  });
  await page.route('**/api/test-live-preview*', route => route.fulfill({ contentType: 'image/svg+xml', body: scanImage }));
  await page.route('**/__scanner-transition', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light"></div></body></html>' }));
  await page.goto('/__scanner-transition');
  await page.evaluate(() => import('/tests/browser/fixtures/importWorkflow.js').then(module => module.mountImportWorkflow({ documents: 0 })));
  await expect(page.locator('.isd-dropzone')).toBeVisible();
  return errors;
}

async function startScan(page, progress = 100, revision = 1) {
  await page.evaluate(({ progress, revision }) => {
    const fixture = window.importFixture;
    fixture.scannerActive.value = true;
    fixture.scanner.value = { ...fixture.scanner.value, scan_progress: progress, live_preview_url: `/api/test-live-preview?v=${revision}` };
  }, { progress, revision });
  await expect(page.locator('.isd-dz-sheet__live-preview')).toBeVisible();
  await expect.poll(() => page.locator('.isd-dz-sheet__live-preview').evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true);
}

async function endScan(page) {
  await page.evaluate(() => {
    const fixture = window.importFixture;
    fixture.scannerActive.value = false;
    fixture.scanner.value = { ...fixture.scanner.value, scan_progress: null, live_preview_url: null };
  });
}

async function addScannerSource(page, previewUrl = '/api/test-thumbnail') {
  await page.evaluate(previewUrl => window.importFixture.component.value.openWithRemoteSources({
    sessionId: 'preview-transition',
    sources: [{ source_file_id: '20000000-0000-4000-8000-000000000001', original_name: 'Scan.pdf', page_count: 1,
      source_type: 'scanner', source_revision: 'revision-1', preview_url: previewUrl }],
  }), previewUrl);
}

test('the completed scan remains visible after the live endpoint disappears', async ({ page }) => {
  const errors = await mount(page);
  await startScan(page);
  const src = await page.locator('.isd-dz-sheet__live-preview').getAttribute('src');
  expect(src).toMatch(/^blob:/);
  await endScan(page);
  await expect(page.locator('.isd-dz-sheet__live-progress')).toHaveText('100%');
  await expect(page.getByText('Scan erfasst', { exact: true })).toBeVisible();
  const frames = await page.evaluate(async () => {
    const result = [];
    for (let index = 0; index < 30; index++) {
      await new Promise(requestAnimationFrame);
      const image = document.querySelector('.isd-dz-sheet__live-preview');
      const opacity = ['.isd-dz-scene', '.isd-dz-sheet--front'].reduce((value, selector) => value * Number(getComputedStyle(document.querySelector(selector)).opacity), 1);
      result.push(Boolean(image?.complete && image.naturalWidth && image.getBoundingClientRect().width && opacity > 0.95));
    }
    return result;
  });
  expect(frames.every(Boolean)).toBe(true);
  expect(await page.locator('.isd-dz-sheet__live-preview').getAttribute('src')).toBe(src);
  expect(errors).toEqual([]);
});

test('the scan moves continuously into the first thumbnail and covers a delayed preview', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const errors = await mount(page);
  let thumbnailRequest;
  await page.route('**/api/test-thumbnail', route => { thumbnailRequest = route; });
  await startScan(page);
  await endScan(page);
  await expect(page.getByText('Scan erfasst', { exact: true })).toBeVisible();
  await page.getByText('Scan erfasst', { exact: true }).evaluate(element => Promise.all(element.parentElement.getAnimations({ subtree: true }).map(animation => animation.finished)));
  const origin = await page.locator('.isd-dz-sheet--front').boundingBox();
  await page.screenshot({ path: '/private/tmp/papermind-scan-finished.png' });
  await page.evaluate(() => {
    window.flightSamples = [];
    const sample = () => {
      const flight = document.querySelector('.isd-scan-flight');
      const thumbnail = document.querySelector('.isd-page-thumb-wrap');
      const visual = flight || document.querySelector('.isd-dz-sheet__live-preview') || document.querySelector('.isd-scan-thumbnail-fallback');
      if (visual) {
        const rect = visual.getBoundingClientRect();
        window.flightSamples.push({ left: rect.left, top: rect.top, width: rect.width,
          flight: Boolean(flight), ready: Boolean(visual.querySelector('img')?.complete || visual.complete),
          target: thumbnail && { left: thumbnail.getBoundingClientRect().left, top: thumbnail.getBoundingClientRect().top } });
      } else window.flightSamples.push(null);
      if (!window.stopFlightSamples) requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  });
  await addScannerSource(page);
  await expect(page.locator('.isd-scan-flight')).toBeVisible();
  await page.screenshot({ path: '/private/tmp/papermind-scan-handoff.png' });
  await expect.poll(() => Boolean(thumbnailRequest)).toBe(true);
  await expect(page.locator('.isd-scan-flight')).toHaveCount(0);
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toBeVisible();
  await page.evaluate(() => { window.stopFlightSamples = true; });
  const samples = await page.evaluate(() => window.flightSamples);
  expect(samples.every(sample => sample?.ready)).toBe(true);
  const flying = samples.filter(sample => sample.flight);
  expect(flying.length).toBeGreaterThan(8);
  expect(Math.abs(flying[0].left - origin.x)).toBeLessThan(10);
  expect(Math.abs(flying.at(-1).left - flying.at(-1).target.left)).toBeLessThan(2);
  expect(Math.abs(flying.at(-1).top - flying.at(-1).target.top)).toBeLessThan(2);
  expect(Math.abs(flying[0].left - flying.at(-1).left)).toBeGreaterThan(100);
  for (let index = 1; index < flying.length; index++) expect(Math.abs(flying[index].left - flying[index - 1].left)).toBeLessThan(100);
  await thumbnailRequest.fulfill({ contentType: 'image/svg+xml', body: scanImage.replace('Scanvorschau', 'Fertige Miniatur') });
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toHaveCount(0);
  await expect(page.locator('.import-staging-page__thumb')).toBeVisible();
  await page.screenshot({ path: '/private/tmp/papermind-scan-thumbnail.png' });
  expect(errors).toEqual([]);
});

test('a quickly loaded thumbnail crossfades only after landing', async ({ page }) => {
  await mount(page);
  await page.route('**/api/test-thumbnail', route => route.fulfill({ contentType: 'image/svg+xml', body: scanImage.replace('Scanvorschau', 'Bereinigte Miniatur') }));
  await startScan(page);
  await endScan(page);
  await addScannerSource(page);
  await expect(page.locator('.isd-scan-flight')).toBeVisible();
  await expect.poll(() => page.locator('.import-staging-page__thumb').evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true);
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toHaveCount(1);
  await page.evaluate(() => new Promise(resolve => {
    const sample = () => {
      const flight = document.querySelector('.isd-scan-flight');
      const fallback = document.querySelector('.isd-scan-thumbnail-fallback');
      if (!flight) return resolve(window.landingCrossfade = Boolean(fallback));
      requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  }));
  expect(await page.evaluate(() => window.landingCrossfade)).toBe(true);
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toHaveCount(0);
});

test('a failed thumbnail keeps the captured scan until retry succeeds', async ({ page }) => {
  const errors = await mount(page);
  await page.route('**/api/test-thumbnail', route => route.fulfill({ status: 404 }));
  await startScan(page);
  await endScan(page);
  await addScannerSource(page);
  await expect(page.locator('.isd-scan-flight')).toHaveCount(0);
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Vorschau erneut laden' })).toBeVisible();
  await page.route('**/api/test-thumbnail-retry', route => route.fulfill({ contentType: 'image/svg+xml', body: scanImage }));
  await page.evaluate(() => { window.importFixture.store.documents[0].pages[0].thumbUrl = '/api/test-thumbnail-retry'; });
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Vorschau erneut laden' })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a final frame that is already in transit can finish after scanner shutdown', async ({ page }) => {
  await mount(page);
  let liveRequest;
  await page.route('**/api/test-live-preview*', route => { liveRequest = route; });
  await page.evaluate(() => {
    window.importFixture.scannerActive.value = true;
    window.importFixture.scanner.value = { ...window.importFixture.scanner.value, scan_progress: 100, live_preview_url: '/api/test-live-preview?v=final' };
  });
  await expect.poll(() => Boolean(liveRequest)).toBe(true);
  await endScan(page);
  await liveRequest.fulfill({ contentType: 'image/svg+xml', body: scanImage });
  await expect(page.locator('.isd-dz-sheet__live-preview')).toBeVisible();
  await expect(page.locator('.isd-dz-sheet__live-progress')).toHaveText('100%');
});

test('a new scan clears the previous frame and rejects a late old response', async ({ page }) => {
  await mount(page);
  await startScan(page, 90);
  const oldFrame = await page.locator('.isd-dz-sheet__live-preview').getAttribute('src');
  let oldRequest;
  await page.route('**/api/test-live-preview?v=old', route => { oldRequest = route; });
  await page.evaluate(() => { window.importFixture.scanner.value = { ...window.importFixture.scanner.value, scan_progress: 100, live_preview_url: '/api/test-live-preview?v=old' }; });
  await expect.poll(() => Boolean(oldRequest)).toBe(true);
  await endScan(page);
  await page.evaluate(() => {
    window.importFixture.scannerActive.value = true;
    window.importFixture.scanner.value = { ...window.importFixture.scanner.value, scan_progress: 0, live_preview_url: null };
  });
  await expect(page.locator('.isd-dz-sheet__live-preview')).toHaveCount(0);
  await oldRequest.fulfill({ contentType: 'image/svg+xml', body: scanImage });
  await startScan(page, 15, 2);
  await expect(page.locator('.isd-dz-sheet__live-progress')).toHaveText('15%');
  expect(await page.locator('.isd-dz-sheet__live-preview').getAttribute('src')).not.toBe(oldFrame);
});

test('an incomplete live frame keeps the last decoded image', async ({ page }) => {
  await mount(page);
  await startScan(page, 75);
  const src = await page.locator('.isd-dz-sheet__live-preview').getAttribute('src');
  await page.route('**/api/test-live-preview?v=broken', route => route.fulfill({ contentType: 'image/png', body: 'incomplete image' }));
  await page.evaluate(() => {
    window.importFixture.scanner.value = { ...window.importFixture.scanner.value, scan_progress: 90, live_preview_url: '/api/test-live-preview?v=broken' };
  });
  await expect(page.locator('.isd-dz-sheet__live-progress')).toHaveText('90%');
  await endScan(page);
  await expect(page.locator('.isd-dz-sheet__live-preview')).toHaveAttribute('src', src);
  await expect(page.locator('.isd-dz-sheet__live-preview')).toBeVisible();
});

test('changing the account clears held scan images and their object URLs', async ({ page }) => {
  await mount(page);
  await startScan(page);
  await endScan(page);
  const src = await page.locator('.isd-dz-sheet__live-preview').getAttribute('src');
  await page.evaluate(() => import('/src/api/session.js').then(module => module.resetApiSession('different-account')));
  await expect(page.locator('.isd-dz-sheet__live-preview')).toHaveCount(0);
  await expect.poll(() => page.evaluate(async src => { try { await fetch(src); return true; } catch { return false; } }, src)).toBe(false);
});

test('removing the imported page never resurrects the completed scan in the start screen', async ({ page }) => {
  await mount(page);
  await startScan(page);
  await endScan(page);
  await addScannerSource(page, '');
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toBeVisible();
  await page.evaluate(() => { window.importFixture.store.reset(); });
  await expect(page.locator('.isd-dropzone')).toBeVisible();
  await expect(page.locator('.isd-dz-sheet__live-preview')).toHaveCount(0);
  await expect(page.locator('.isd-scan-flight')).toHaveCount(0);
});

test('an unrelated PDF never receives the retained scanner image', async ({ page }) => {
  await mount(page);
  await startScan(page);
  await endScan(page);
  await page.evaluate(() => {
    window.importFixture.store.addDocumentFromSource({ sourceFileId: 'unrelated-pdf', title: 'Upload', pageCount: 1, thumbUrls: [] });
  });
  await expect(page.locator('.isd-page-card')).toHaveCount(1);
  await expect(page.locator('.isd-scan-flight')).toHaveCount(0);
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toHaveCount(0);
});

test('the animated handoff also lands within the mobile thumbnail row', async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 900 });
  const errors = await mount(page);
  await startScan(page);
  await endScan(page);
  await addScannerSource(page, '');
  await expect(page.locator('.isd-scan-flight')).toBeVisible();
  await expect(page.locator('.isd-scan-flight')).toHaveCount(0);
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toBeVisible();
  const rect = await page.locator('.isd-scan-thumbnail-fallback').boundingBox();
  expect(rect.x).toBeGreaterThanOrEqual(0);
  expect(rect.x + rect.width).toBeLessThanOrEqual(430);
  expect(rect.y).toBeGreaterThanOrEqual(0);
  expect(rect.y + rect.height).toBeLessThanOrEqual(900);
  await page.screenshot({ path: '/private/tmp/papermind-scan-mobile.png' });
  expect(errors).toEqual([]);
});

for (const mode of ['reduced-motion', 'disabled-animations']) test(`${mode} reveals the first thumbnail without a flight or a gap`, async ({ page }) => {
  await page.setViewportSize({ width: 430, height: 900 });
  if (mode === 'reduced-motion') await page.emulateMedia({ reducedMotion: 'reduce' });
  else await page.addInitScript(() => localStorage.setItem('pm.animationsEnabled', '0'));
  await mount(page);
  await startScan(page);
  await endScan(page);
  await addScannerSource(page, '');
  await expect(page.locator('.isd-scan-flight')).toHaveCount(0);
  await expect(page.locator('.isd-scan-thumbnail-fallback')).toBeVisible();
  await expect(page.locator('.isd-page-thumb-wrap')).toBeVisible();
});

test('closing during the handoff removes the floating image and releases its memory', async ({ page }) => {
  await mount(page);
  await startScan(page);
  await endScan(page);
  const src = await page.locator('.isd-dz-sheet__live-preview').getAttribute('src');
  await addScannerSource(page, '');
  await expect(page.locator('.isd-scan-flight')).toBeVisible();
  await page.evaluate(() => { window.importFixture.open.value = false; });
  await expect(page.locator('.isd-scan-flight')).toHaveCount(0);
  await expect.poll(() => page.evaluate(async src => { try { await fetch(src); return true; } catch { return false; } }, src)).toBe(false);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => window.importFixture.store.documents.length)).toBe(0);
  await page.evaluate(() => { window.importFixture.open.value = true; });
  await expect(page.locator('.isd-dropzone')).toBeVisible();
  await expect(page.locator('.isd-dz-sheet__live-preview')).toHaveCount(0);
});
