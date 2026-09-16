import { expect, test } from '@playwright/test';

test('review focus dims rich content and nested siblings without dimming the anchor', async ({ page }) => {
  await page.route('**/__review-focus', (route) => route.fulfill({
    contentType: 'text/html',
    body: '<html><body><div id="editor" class="note-editor note-editor--review-active note-editor--review-dim"></div></body></html>',
  }));
  await page.goto('/__review-focus');
  await page.evaluate(async () => {
    const { mountReviewFocus } = await import('/tests/browser/fixtures/noteReviewFocus.js');
    mountReviewFocus();
  });
  const opacity = (selector) => page.locator(selector).first().evaluate((el) => {
    let value = 1;
    for (let node = el; node; node = node.parentElement) value *= Number(getComputedStyle(node).opacity);
    return value;
  });
  for (const selector of ['h2', 'blockquote p', 'a .pm-review-muted', 'th p', 'td p', 'img', 'li li p', 'ul > li:nth-child(2) p', 'pre code', '.pm-review-muted']) {
    expect(await opacity(selector), selector).toBeLessThanOrEqual(0.28);
  }
  expect(await opacity('.pm-review-underline.is-focus')).toBe(1);
  expect(await opacity('.pm-review-num.is-focus')).toBe(1);
  await expect(page.getByText('Davor', { exact: true })).toHaveClass(/pm-review-muted/);
  await page.evaluate(() => {
    const { editor, setReviewDecorations, from } = window.reviewFixture;
    setReviewDecorations(editor, [{ id: 1, from, to: from + 5, class: 'pm-review-underline' }]);
  });
  await expect(page.locator('.pm-review-muted')).toHaveCount(0);
  expect(await opacity('h2')).toBe(1);
  await page.evaluate(() => window.reviewFixture.clearReviewDecorations(window.reviewFixture.editor));
  await expect(page.locator('.pm-review-underline')).toHaveCount(0);
});
