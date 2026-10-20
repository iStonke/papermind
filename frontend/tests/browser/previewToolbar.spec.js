import { test, expect } from '@playwright/test';

function syntheticPdf() {
  const content = 'BT /F1 20 Tf 50 760 Td (Shared toolbar sample) Tj ET';
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', `<< /Length ${content.length} >>\nstream\n${content}\nendstream`];
  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(pdf);
}

async function mountPdf(page, reader = false) {
  await page.route('**/toolbar-test.pdf', route => route.fulfill({ contentType: 'application/pdf', body: syntheticPdf() }));
  await page.route(url => url.pathname.startsWith('/api/'), route => route.fulfill({ json: { items: [] } }));
  await page.route('**/__preview-toolbar', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app"></div></body></html>' }));
  await page.goto('/__preview-toolbar');
  await page.evaluate(reader => import('/tests/browser/fixtures/previewToolbar.js').then(module => module.mountPreviewToolbar({ reader })), reader);
  await expect(page.locator('.pdf-preview__viewer')).toHaveClass(/--ready/);
  return page.getByRole('toolbar', { name: 'PDF-Steuerung' });
}

for (const reader of [false, true]) test(`shared PDF tools preserve zoom, search and focus in ${reader ? 'reader' : 'document preview'}`, async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const toolbar = await mountPdf(page, reader);
  await page.mouse.move(0, 0);
  await expect(toolbar).toHaveCSS('opacity', '0');
  await page.locator('.pdf-preview__pages').hover();
  await expect(toolbar).toHaveCSS('opacity', '1');
  await toolbar.getByRole('button', { name: 'Vergrößern', exact: true }).click();
  await expect(toolbar.getByRole('button', { name: /Zoom 112 Prozent/ })).toBeVisible();
  await toolbar.getByRole('button', { name: /Zoom 112 Prozent/ }).click();
  await expect(toolbar.getByRole('button', { name: /Zoom 100 Prozent/ })).toBeVisible();
  await toolbar.getByRole('button', { name: 'Im Dokument suchen', exact: true }).click();
  await page.getByRole('textbox', { name: 'Suchbegriff' }).fill('Shared');
  await page.mouse.move(0, 0);
  await expect(toolbar).toHaveCSS('opacity', '1');
  await expect(page.locator('.pdf-preview__match-badge')).toContainText('1');
  await toolbar.getByRole('button', { name: 'Suche schließen', exact: true }).click();
  await page.locator('.pdf-preview__pages').focus();
  await page.keyboard.press('Shift+Tab');
  await expect(toolbar).toHaveCSS('opacity', '1');
  expect(await toolbar.evaluate(element => element.contains(document.activeElement))).toBe(true);
});

test.describe('touch PDF preview', () => {
  test.use({ viewport: { width: 430, height: 900 }, hasTouch: true });
  test('keeps tools visible and inside the preview in both themes', async ({ page }) => {
    const toolbar = await mountPdf(page);
    for (const theme of ['dark', 'light']) {
      await page.evaluate(theme => window.previewToolbarFixture.setTheme(theme), theme);
      await expect(toolbar).toHaveCSS('opacity', '1');
      expect(await toolbar.evaluate(element => {
        const rect = element.getBoundingClientRect();
        const parent = element.parentElement.getBoundingClientRect();
        return rect.left >= parent.left && rect.right <= parent.right && [...element.querySelectorAll('button')].every(button => {
          const bounds = button.getBoundingClientRect();
          return bounds.left >= rect.left && bounds.right <= rect.right;
        });
      })).toBe(true);
      await toolbar.getByRole('button', { name: 'Vergrößern', exact: true }).tap();
      await toolbar.getByRole('button', { name: /Zoom .* Prozent/ }).tap();
    }
  });
});
