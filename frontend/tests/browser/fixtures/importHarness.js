import { expect } from '@playwright/test';

export async function mount(page, options = {}) {
  const requests = [];
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes('/color-preview')) return route.fulfill({ status: 404, body: '' });
    if (path.endsWith('/suggest-title')) return route.fulfill({ json: { status: 'ready', suggestion: '', meta: {} } });
    if (path === '/api/import/commit') {
      const body = route.request().postDataJSON();
      requests.push(body);
      return route.fulfill({ json: { created: body.documents.map(doc => ({ client_document_id: doc.client_document_id, doc_id: `saved-${doc.client_document_id}`, title: doc.title, page_count: doc.pages.length })), errors: [] } });
    }
    return route.fulfill({ json: { items: [] } });
  });
  await page.route('**/__import-workflow', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light"></div></body></html>' }));
  await page.goto('/__import-workflow');
  await page.evaluate(options => import('/tests/browser/fixtures/importWorkflow.js').then(module => module.mountImportWorkflow(options)), options);
  await expect(page.getByRole('button', { name: /^(Importieren|Importstatus prüfen)$/ })).toBeVisible();
  return requests;
}

export async function revealImportTools(page) {
  await page.locator('.isd-preview-panel').hover();
  await expect(page.getByRole('toolbar', { name: 'Seitenwerkzeuge' })).toHaveCSS('opacity', '1');
}
export async function startImportAnalysis(page) {
  await page.locator('.isd-props-heading .isd-ai-status-btn').click();
}

export async function completeRequiredMetadata(page) {
  await page.evaluate(() => {
    const { store, correspondents } = window.importFixture;
    correspondents.correspondents = [{ id: '30000000-0000-4000-8000-000000000001', name: 'Testfirma', kind: 'organization' }];
    for (const doc of store.documents) {
      Object.assign(doc.meta.form, { date: '20.10.2026', category: 'Brief', correspondentId: correspondents.correspondents[0].id });
      doc.meta.pendingTagNames = ['Unterlagen'];
    }
  });
}
