import { test, expect } from '@playwright/test';

test('activity visibility follows running and paused jobs', async ({ page }) => {
  let jobs = [];
  const actions = [];
  let background = [];
  await page.route('**/api/jobs/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === 'POST') {
      actions.push(path);
      if (path.endsWith('/restart')) return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: { message: 'Ein Vorgang läuft bereits.' } }) });
      jobs = jobs.map(job => ({ ...job, status: 'failed', error_message: 'Vom Nutzer beendet' }));
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ jobs, audio_exports: [], background, ocr_backlog: {} }) });
  });
  await page.route('**/__activity', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="v-theme--light" style="padding:40px"></div></body></html>' }));
  await page.goto('/__activity');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/activity.js')).mountActivity());
  await expect(page.locator('.activity-indicator-btn')).toHaveCount(0);
  background = [{ id: 'paused-1', kind: 'wiki', title: 'Wissensaufbau', status: 'paused' }];
  await page.evaluate(() => window.dispatchEvent(new Event('papermind:activity-refresh')));
  await expect(page.locator('.activity-indicator-btn')).toBeVisible();
  jobs = [{ id: 'job-1', document_id: 'doc-1', document_title: 'Rechnung', type: 'OCR', status: 'running' }];
  await page.evaluate(() => window.dispatchEvent(new Event('papermind:activity-refresh')));
  await page.locator('.activity-indicator-btn').click();
  await expect(page.getByText('Rechnung')).toBeVisible();
  await page.getByRole('button', { name: 'Dokumentverarbeitung beenden' }).click();
  await expect(page.getByText('Vom Nutzer beendet')).toBeVisible();
  await page.getByRole('button', { name: 'Dokumentverarbeitung neu starten' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  expect(actions).toEqual(['/api/jobs/job-1/cancel', '/api/jobs/job-1/restart']);
  background = [];
  await page.getByRole('button', { name: 'Aktivität aktualisieren' }).click();
  await expect(page.locator('.activity-indicator-btn')).toHaveCount(0);
});

test('background controls and narrow dark menu', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 740 });
  const actions = [];
  const background = [
    { id: 'wiki-1', kind: 'wiki', title: 'Wissensaufbau', status: 'running', progress: 25 },
    { id: 'backup-1', kind: 'backup', title: 'NAS-Backup', status: 'running' },
    { id: 'import-1', kind: 'preanalysis', title: 'Importanalyse', status: 'cancelled' },
  ];
  await page.route('**/api/jobs/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === 'POST') {
      actions.push(path);
      if (path.endsWith('/pause')) background[0].status = 'paused';
      if (path.endsWith('/resume')) background[0].status = 'queued';
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ jobs: [{ id: 'ocr-1', document_id: 'document-1', document_title: 'Rechnung', type: 'OCR', status: 'running' }], audio_exports: [{ id: 'audio-1', note_title: 'Besprechung', status: 'queued' }], background, ocr_backlog: { pending: 1, total: 520, done: 517, failed: 2 } }) });
  });
  await page.route('**/__activity', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" style="padding:12px"></div></body></html>' }));
  await page.goto('/__activity');
  await page.evaluate(async () => (await import('/tests/browser/fixtures/activity.js')).mountActivity('dark'));
  await page.getByRole('button', { name: /Vorgang\/Vorgänge/ }).click();
  await page.getByRole('button', { name: 'Wissensaufbau pausieren' }).click();
  await expect(page.getByText('Pausiert')).toBeVisible();
  await page.getByRole('button', { name: 'Wissensaufbau fortsetzen' }).click();
  await page.getByRole('button', { name: 'NAS-Backup beenden' }).click();
  await page.getByRole('button', { name: 'Laufend', exact: true }).click();
  await expect(page.getByText('Importanalyse')).not.toBeVisible();
  await expect(page.locator('.activity-card .v-progress-linear:visible')).toHaveCount(0);
  await expect(page.locator('.activity-item__title').filter({ hasText: 'Texterkennung' })).toBeVisible();
  await expect(page.locator('.activity-item__title').filter({ hasText: 'Audioexport' })).toBeVisible();
  const rect = await page.locator('.activity-card').boundingBox();
  expect(rect.x).toBeGreaterThanOrEqual(0);
  expect(rect.x + rect.width).toBeLessThanOrEqual(375);
  expect(actions).toHaveLength(3);
  await page.screenshot({ path: '/tmp/papermind-activity-dark.png' });
});
