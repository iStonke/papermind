import { expect, test } from '@playwright/test';

async function openPanel(page) {
  await page.route('**/__review-decisions', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app" class="papermind-app v-theme--light" style="width:380px;height:700px"></div></body></html>' }));
  await page.goto('/__review-decisions');
  await page.evaluate(async () => { const { mountDecisions } = await import('/tests/browser/fixtures/reviewDecisions.js'); mountDecisions(); });
}

test('accept and reject share motion with distinct colors and commit immediately', async ({ page }) => {
  await openPanel(page);
  let acceptedMotion;
  let acceptedColor;
  for (const [id, label, kind, className] of [[1, 'Annehmen', 'accept', 'is-accepted'], [2, 'Ablehnen', 'reject', 'is-dismissed']]) {
    await page.locator(`[data-review-id="${id}"]`).click();
    // Dispatch synchronously so the short animation can be inspected reliably.
    await page.getByRole('button', { name: label, exact: true }).evaluate(el => el.click());
    expect(await page.evaluate(() => window.decisions.at(-1))).toEqual([kind, id]);
    const ghost = page.locator('.pm-review-card--decision');
    const frames = await ghost.evaluate(el => {
      const animation = el.getAnimations()[0];
      animation.pause();
      return animation.effect.getKeyframes();
    });
    await expect(ghost).toHaveClass(new RegExp(className));
    await expect(ghost).toHaveAttribute('aria-hidden', 'true');
    expect(frames.at(-1).transform).toContain('scale(1)');
    const motion = frames.map(frame => [frame.transform, frame.offset]);
    const color = await ghost.evaluate(el => getComputedStyle(el).backgroundColor);
    if (kind === 'accept') { acceptedMotion = motion; acceptedColor = color; }
    else { expect(motion).toEqual(acceptedMotion); expect(color).not.toBe(acceptedColor); }
    await ghost.evaluate(el => el.getAnimations()[0].finish());
    await expect(ghost).toHaveCount(0);
  }
  await page.locator('[data-review-id="3"]').click();
  await page.getByRole('button', { name: 'Annehmen', exact: true }).evaluate(el => el.click());
  await page.evaluate(() => window.reviewFixture.unmount());
  await expect(page.locator('.pm-review-card--decision')).toHaveCount(0);
});

for (const mode of ['system', 'app']) {
  test(`reduced motion (${mode}) commits without a decorative copy`, async ({ page }) => {
    if (mode === 'system') await page.emulateMedia({ reducedMotion: 'reduce' });
    await openPanel(page);
    if (mode === 'app') await page.locator('#app').evaluate(el => el.classList.add('pm-no-animations'));
    await page.getByRole('button', { name: 'Annehmen', exact: true }).click();
    expect(await page.evaluate(() => window.decisions)).toEqual([['accept', 1]]);
    await expect(page.locator('.pm-review-card--decision')).toHaveCount(0);
  });
}
