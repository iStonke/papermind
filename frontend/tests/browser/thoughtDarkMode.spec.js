import { expect, test } from '@playwright/test';
import { openThoughts } from './helpers/thoughtSummary.js';
import { THOUGHT_COLORS } from '../../src/utils/thoughtColors.js';

async function contrasts(locator, pseudo = null) {
  return locator.evaluateAll((elements, pseudo) => elements.map(element => {
    const style = getComputedStyle(element, pseudo);
    let surface = element;
    while (surface && getComputedStyle(surface).backgroundColor === 'rgba(0, 0, 0, 0)') surface = surface.parentElement;
    const rgb = color => {
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 1;
      const context = canvas.getContext('2d');
      context.fillStyle = color; context.fillRect(0, 0, 1, 1);
      return [...context.getImageData(0, 0, 1, 1).data].slice(0, 3);
    };
    const luminance = color => rgb(color).map(value => {
      const channel = value / 255;
      return channel <= .04045 ? channel / 12.92 : ((channel + .055) / 1.055) ** 2.4;
    }).reduce((total, channel, index) => total + channel * [.2126, .7152, .0722][index], 0);
    const text = luminance(style.color), background = luminance(getComputedStyle(surface).backgroundColor);
    return (Math.max(text, background) + .05) / (Math.min(text, background) + .05);
  }), pseudo);
}

test('theme switching keeps text, date, and selection readable for every header color', async ({ page }) => {
  await openThoughts(page, [null, ...THOUGHT_COLORS.map(color => color.value)]);
  for (const mode of ['dark', 'light', 'dark']) {
    await page.evaluate(mode => window.setThoughtsTheme(mode), mode);
    for (const selector of ['.thoughts-text', '.thoughts-card time', '.notes-ws__item-title', '.notes-ws__item-snippet']) {
      const elements = page.locator(selector);
      expect(await elements.count()).toBeGreaterThan(0);
      for (const contrast of await contrasts(elements)) expect(contrast).toBeGreaterThanOrEqual(4.5);
    }
    if (mode === 'dark') {
      const colors = await page.locator('article.thoughts-card').first().evaluate(card => ({
        card: getComputedStyle(card).backgroundColor,
        canvas: getComputedStyle(document.querySelector('.thoughts-ws')).backgroundColor,
      }));
      expect(colors.card).not.toBe(colors.canvas);
    }
  }
  await page.locator('.thoughts-text').first().click({ modifiers: ['Shift'] });
  const selected = page.locator('article.thoughts-card.is-selected').first();
  await expect(selected).toBeVisible();
  const accent = await selected.evaluate(card => ({ border: getComputedStyle(card).borderColor }));
  expect(accent.border).toBe('rgb(79, 197, 203)');
});

test('editing, new thoughts, palette and summary dialog follow dark mode', async ({ page }) => {
  await openThoughts(page, ['#cce0dc', '#efd2dc']);
  await page.evaluate(() => window.setThoughtsTheme('dark'));
  await page.locator('.thoughts-text').first().click();
  await expect(page.getByRole('textbox', { name: 'Gedanken bearbeiten' })).toBeVisible();
  expect((await contrasts(page.locator('.thoughts-edit')))[0]).toBeGreaterThanOrEqual(4.5);
  await page.locator('.thoughts-canvas').click({ position: { x: 20, y: 400 } });
  await page.locator('article.thoughts-card').first().hover();
  await page.locator('article.thoughts-card').first().getByRole('button', { name: 'Titelleistenfarbe wählen' }).click();
  const palette = page.getByRole('group', { name: 'Titelleistenfarbe', exact: true });
  await expect(palette).toHaveClass(/v-theme--dark/);
  const darkHeader = await page.locator('.thoughts-titlebar').first().evaluate(el => getComputedStyle(el).backgroundColor);
  expect(darkHeader).not.toBe('rgb(204, 224, 220)');
  expect(await palette.getByRole('button', { name: 'Salbei', exact: true }).evaluate(el => getComputedStyle(el).backgroundColor)).toBe(darkHeader);
  expect(await palette.evaluate(element => getComputedStyle(element).backgroundColor)).toBe('rgb(51, 59, 62)');
  await page.evaluate(() => window.setThoughtsTheme('light'));
  await expect(palette).toHaveClass(/v-theme--light/);
  expect(await page.locator('.thoughts-titlebar').first().evaluate(el => getComputedStyle(el).backgroundColor)).toBe('rgb(204, 224, 220)');
  await page.evaluate(() => window.setThoughtsTheme('dark'));
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Alle Gedanken zusammenfassen', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Titel der neuen Notiz' })).toHaveValue('Generierter Titel');
  await expect(page.getByRole('dialog')).toHaveClass(/v-theme--dark/);
  await page.getByRole('button', { name: 'Zurück', exact: true }).click();
  await page.getByRole('button', { name: 'Neuer Gedanke', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Gedanken festhalten' })).toBeVisible();
  for (const contrast of await contrasts(page.locator('.thoughts-capture textarea'), '::placeholder')) expect(contrast).toBeGreaterThanOrEqual(4.5);
});
