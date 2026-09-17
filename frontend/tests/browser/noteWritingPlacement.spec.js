import { expect, test } from '@playwright/test';

test('writing prompt stays reachable near the bottom, on growth, scroll and resize', async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 600 });
  await page.route('**/__writing-placement', (route) => route.fulfill({
    contentType: 'text/html',
    body: '<html><body style="margin:0"><main class="papermind-app" style="--pm-app-surface-raised:rgb(30, 40, 50)"><div id="app"></div></main></body></html>',
  }));
  await page.goto('/__writing-placement');
  await page.evaluate(async () => {
    const { mountWritingPlacement } = await import('/tests/browser/fixtures/noteWritingPlacement.js');
    mountWritingPlacement();
  });
  const prompt = page.locator('.pm-ai-prompt--writing');
  const fits = async () => {
    await expect(prompt).toBeVisible();
    await expect.poll(() => prompt.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      return rect.top >= 7 && rect.left >= 7
        && rect.bottom <= innerHeight - 7 && rect.right <= innerWidth - 7;
    })).toBe(true);
  };
  await fits();
  await expect(prompt).toHaveCSS('background-color', 'rgb(30, 40, 50)');
  await expect(page.getByPlaceholder('Was soll PaperMind schreiben?')).toBeFocused();
  expect((await prompt.boundingBox()).y).toBeLessThan(450);
  await page.evaluate(() => { window.writing.aiPrompt.error = 'Eine lange Fehlermeldung. '.repeat(60); });
  await fits();
  await page.setViewportSize({ width: 360, height: 300 });
  await fits();
  await page.evaluate(() => { document.querySelector('#surface').scrollTop = 100; });
  await fits();
  await prompt.locator('.pm-ai-prompt__error').scrollIntoViewIfNeeded();
  await fits();
  await page.evaluate(() => window.writing.closeAIPrompt());
  await expect(prompt).toHaveCount(0);
});
