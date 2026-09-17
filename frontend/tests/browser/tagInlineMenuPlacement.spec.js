import { expect, test } from '@playwright/test';

async function mountFixture(page, placement) {
  await page.route('**/__tag-inline-menu', (route) => route.fulfill({
    contentType: 'text/html',
    body: '<html><body style="margin:0"><div id="app"></div></body></html>',
  }));
  await page.goto('/__tag-inline-menu');
  await page.evaluate(async (position) => {
    const { mountTagInlineMenu } = await import('/tests/browser/fixtures/tagInlineMenuPlacement.js');
    mountTagInlineMenu(position);
  }, placement);
  const input = page.locator('.pm-tags-input__field input');
  await input.click();
  await input.fill('Agile');
  await expect(page.locator('.pm-tag-inline-menu')).toBeVisible();
  await expect.poll(() => page.locator('.pm-tag-inline-menu').evaluate((el) => (
    Math.round(el.getBoundingClientRect().width)
  ))).toBe(320);
  const verticalAlignment = await page.evaluate(() => {
    const field = document.querySelector('.pm-tags-input__field').getBoundingClientRect();
    const input = document.querySelector('.pm-tags-input__field input').getBoundingClientRect();
    return {
      centerDelta: Math.abs((field.top + field.height / 2) - (input.top + input.height / 2)),
      inputHeight: input.height,
    };
  });
  expect(verticalAlignment.centerDelta).toBeLessThanOrEqual(1);
  expect(verticalAlignment.inputHeight).toBe(26);
}

test('tag suggestions form a compact menu above a field near the viewport bottom', async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 500 });
  await mountFixture(page, 'bottom');
  const field = await page.locator('.pm-tags-input__field').boundingBox();
  const menu = await page.locator('.pm-tag-inline-menu').boundingBox();
  expect(field.width).toBeLessThanOrEqual(181);
  expect(menu.width).toBeGreaterThanOrEqual(259);
  expect(menu.width).toBeLessThanOrEqual(361);
  expect(menu.y + menu.height).toBeLessThanOrEqual(field.y);
  expect(field.y - (menu.y + menu.height)).toBeLessThanOrEqual(8);
  expect(menu.height).toBeLessThanOrEqual(48);
});

test('tag suggestions open below when sufficient space is available', async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 500 });
  await mountFixture(page, 'top');
  const field = await page.locator('.pm-tags-input__field').boundingBox();
  const menu = await page.locator('.pm-tag-inline-menu').boundingBox();
  expect(menu.y).toBeGreaterThanOrEqual(field.y + field.height);
  expect(menu.y - (field.y + field.height)).toBeLessThanOrEqual(8);
});
