import { expect, test } from '@playwright/test';
import { defaultSpeechOptions } from '../../src/utils/speechSettings.js';

function wav() {
  const buffer = Buffer.alloc(44 + 16000);
  buffer.write('RIFF'); buffer.writeUInt32LE(buffer.length - 8, 4); buffer.write('WAVEfmt ', 8);
  buffer.writeUInt32LE(16, 16); buffer.writeUInt16LE(1, 20); buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(8000, 24); buffer.writeUInt32LE(16000, 28);
  buffer.writeUInt16LE(2, 32); buffer.writeUInt16LE(16, 34); buffer.write('data', 36); buffer.writeUInt32LE(16000, 40);
  return buffer;
}
async function mount(page, { full = true, dark = false, block = false, realAudio = false, failedSave = false, initial = {} } = {}) {
  const speech = [], patches = [];
  const persisted = { ui: { notes_tts_voice: 'neutral', notes_tts_language_mode: 'de', notes_tts_options: defaultSpeechOptions(), ...initial } };
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === '/api/tts/engines') return route.fulfill({ json: { items: [
      { id: 'piper', name: 'Piper', available: true }, { id: 'kokoro', name: 'Thorsten Kokoro', available: true },
      { id: 'cosyvoice', name: 'Thorsten CosyVoice', available: false },
    ] } });
    if (path === '/api/tts/speech') {
      speech.push(request.postDataJSON());
      await new Promise(resolve => setTimeout(resolve, 120));
      return route.fulfill({ contentType: 'audio/wav', body: wav(), headers: {
        'X-Speech-Duration': '1', 'X-Speech-Generation-Ms': '120', 'X-Speech-Engine': speech.at(-1).options.engine,
      } });
    }
    if (path === '/api/settings') {
      if (request.method() === 'PATCH') {
        patches.push(request.postDataJSON());
        if (failedSave) return route.fulfill({ status: 500, json: { error: { message: 'Speichern fehlgeschlagen' } } });
        Object.assign(persisted.ui, request.postDataJSON().ui);
      }
      return route.fulfill({ json: persisted });
    }
    return route.fulfill({ json: { items: [] } });
  });
  await page.route('**/__speech-settings', route => route.fulfill({ contentType: 'text/html',
    body: '<div id="app" class="papermind-app" style="max-width:1000px;margin:auto;padding:20px"></div>' }));
  await page.goto('/__speech-settings');
  await page.evaluate(async ({ full, dark, block, realAudio, initial }) => {
    window.speechSettingsPlays = [];
    if (!realAudio) {
      HTMLMediaElement.prototype.play = function() {
        window.speechSettingsPlays.push({ element: this, src: this.src, active: navigator.userActivation.isActive });
        return block && this.src.startsWith('blob:') ? Promise.reject(new DOMException('blocked', 'NotAllowedError')) : Promise.resolve();
      };
      HTMLMediaElement.prototype.pause = function() {};
      HTMLMediaElement.prototype.load = function() {};
    }
    (await import('/tests/browser/fixtures/speechSettings.js')).mountSpeechSettings({ full, dark, initial });
  }, { full, dark, block, realAudio, initial: persisted.ui });
  await expect(page.getByRole('heading', { name: 'Stimme und Sprache' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Mit Piper hören' })).toBeEnabled();
  return { speech, patches, persisted };
}

test('central preferences persist and are used for voice previews and comparisons', async ({ page }) => {
  const { speech, patches, persisted } = await mount(page);
  await expect(page.getByRole('tab', { name: 'Sprachausgabe', exact: true })).toHaveAttribute('aria-selected', 'true');
  await page.waitForTimeout(400);
  await page.screenshot({ path: '../.runtime/speech-settings/desktop-light.png', fullPage: true, animations: 'disabled' });
  await page.locator('#speech-speed').fill('1.15');
  await page.locator('#speech-speed').dispatchEvent('change');
  await expect.poll(() => patches.length).toBe(1);
  expect(patches[0].ui.notes_tts_options.speed).toBe(1.15);
  await page.getByLabel('Wort oder Wortgruppe', { exact: true }).fill('QIS');
  await page.getByLabel('Gesprochene Form', { exact: true }).fill('Kiss');
  await page.getByRole('button', { name: 'Eintrag hinzufügen' }).click();
  await expect.poll(() => patches.length).toBe(2);
  await page.getByRole('button', { name: 'Hörprobe der gewählten Stimme' }).click();
  await expect(page.locator('audio')).toBeVisible();
  await page.getByRole('button', { name: 'Mit Thorsten Kokoro hören' }).click();
  await expect.poll(() => speech.length).toBe(2);
  await expect(page.locator('.speech-metrics')).toHaveCount(2);
  expect(speech[0].voice).toBe('neutral');
  expect(speech[0].language_mode).toBe('de');
  expect(speech[0].options.speed).toBe(1.15);
  expect(speech[0].options.pronunciations[0].pronunciation).toBe('Kiss');
  expect(speech[0].text).toBe(speech[1].text);
  expect(speech[1].options).toEqual({ ...speech[0].options, engine: 'kokoro' });
  expect(await page.evaluate(() => window.speechSettingsPlays[0].active)).toBe(true);
  expect(await page.evaluate(() => window.speechSettingsPlays[0].element === window.speechSettingsPlays[1].element)).toBe(true);
  await expect(page.getByRole('button', { name: 'Mit Thorsten CosyVoice hören' })).toBeDisabled();
  await page.getByRole('tab', { name: 'Allgemein', exact: true }).click();
  await expect(page.getByLabel('Deutsche Stimme')).toHaveCount(0);
  await page.getByRole('tab', { name: 'Sprachausgabe', exact: true }).click();
  await expect(page.locator('#speech-speed')).toHaveValue('1.15');
  await expect(page.locator('.speech-entry')).toContainText('QIS');
  expect(persisted.ui.notes_tts_options.pronunciations).toHaveLength(1);
});

test('blocked playback retains usable audio, changing preferences cancels a stale preview', async ({ page }) => {
  const { speech } = await mount(page, { full: false, block: true });
  await page.getByRole('button', { name: 'Hörprobe der gewählten Stimme' }).click();
  await expect(page.locator('.speech-error[role="alert"]')).toContainText('Die Hörprobe ist bereit');
  await expect(page.locator('audio')).toBeVisible();
  expect(speech).toHaveLength(1);
  await page.getByRole('button', { name: 'Mit Thorsten Kokoro hören' }).click();
  await page.getByLabel('Text für die Hörprobe').fill('Ein neuer Text.');
  await page.waitForTimeout(250);
  await expect(page.locator('audio')).not.toBeVisible();
  await expect(page.locator('.speech-metrics')).toHaveCount(0);
});

test('failed preference saves restore the previous value', async ({ page }) => {
  await mount(page, { failedSave: true });
  await page.locator('#speech-speed').fill('1.2');
  await page.locator('#speech-speed').dispatchEvent('change');
  await expect(page.locator('#speech-speed')).toHaveValue('1');
});

test('preview decodes a real WAV after the delayed request', async ({ page }) => {
  await mount(page, { full: false, realAudio: true });
  await page.getByRole('button', { name: 'Hörprobe der gewählten Stimme' }).click();
  await expect(page.locator('audio')).toBeVisible();
  await expect.poll(() => page.locator('audio').evaluate(audio => audio.readyState)).toBeGreaterThanOrEqual(2);
  await expect(page.locator('.speech-error[role="alert"]')).toHaveCount(0);
});

test('dictionary edit, toggle and deletion remain usable on a narrow dark panel', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { patches } = await mount(page, { full: false, dark: true, initial: { notes_tts_options: {
    ...defaultSpeechOptions(), pronunciations: [{ word: 'QIS', pronunciation: 'Kiss', case_sensitive: false, enabled: true }],
  } } });
  await page.getByRole('button', { name: 'Aussprache für QIS bearbeiten' }).click();
  await page.getByLabel('Gesprochene Form', { exact: true }).fill('Kwis');
  await page.getByRole('button', { name: 'Eintrag übernehmen' }).click();
  await expect(page.locator('.speech-entry')).toContainText('Kwis');
  await page.getByLabel('Aussprache für QIS aktivieren').uncheck();
  await expect.poll(() => patches.at(-1)?.ui.notes_tts_options.pronunciations[0].enabled).toBe(false);
  await page.getByRole('button', { name: 'Aussprache für QIS löschen' }).click();
  await expect(page.locator('.speech-entry')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '../.runtime/speech-settings/narrow-dark.png', fullPage: true });
});
