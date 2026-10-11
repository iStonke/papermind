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
async function mount(page, { full = true, dark = false, block = false, realAudio = false, piperOnly = false, failedSave = false, deferSpeech = false, initial = {} } = {}) {
  const speech = [], patches = [], pendingSpeech = [];
  const persisted = { ui: { notes_tts_voice: 'neutral', notes_tts_language_mode: 'de', notes_tts_options: defaultSpeechOptions(), ...initial } };
  await page.route(/^https?:\/\/[^/]+\/api\//, async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === '/api/tts/engines') return route.fulfill({ json: { items: [
      { id: 'piper', name: 'Piper', available: true }, { id: 'kokoro', name: 'Thorsten Kokoro', available: true },
      { id: 'cosyvoice', name: 'Thorsten CosyVoice', available: false },
    ].filter(engine => !piperOnly || engine.id === 'piper') } });
    if (path === '/api/tts/speech') {
      speech.push(request.postDataJSON());
      if (deferSpeech) await new Promise(resolve => pendingSpeech.push(resolve));
      else await new Promise(resolve => setTimeout(resolve, 120));
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
  await expect(page.getByRole('combobox', { name: 'Deutsche Stimme', exact: true })).toBeEnabled();
  return { speech, patches, persisted, releaseSpeech: index => pendingSpeech[index]() };
}

async function choose(page, label, option) {
  const control = page.getByRole('combobox', { name: label, exact: true });
  await expect(control).toBeEnabled();
  await control.press('Enter');
  await page.getByRole('option', { name: option, exact: true }).click();
}
async function expectSample(page, count = 1) {
  await expect.poll(() => page.evaluate(() => window.speechSettingsPlays.filter(play => play.src.startsWith('blob:')).length)).toBe(count);
}

test('selecting a voice immediately reads a standard text with the saved settings', async ({ page }) => {
  const { speech, patches, persisted } = await mount(page);
  await expect(page.getByRole('tab', { name: 'Sprachausgabe', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('heading', { name: 'Hörprobe', exact: true })).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: 'Text für die Hörprobe' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Hörprobe abspielen' })).toHaveCount(0);
  expect(speech).toHaveLength(0);
  await page.waitForTimeout(400);
  await page.screenshot({ path: '../.runtime/speech-settings/desktop-light.png', fullPage: true, animations: 'disabled' });
  await page.locator('#speech-speed').fill('1.15');
  await page.locator('#speech-speed').dispatchEvent('change');
  await expect.poll(() => patches.length).toBe(1);
  await page.getByText('Eigenes Aussprachewörterbuch', { exact: true }).click();
  await page.getByLabel('Wort oder Wortgruppe', { exact: true }).fill('QIS');
  await page.getByLabel('Gesprochene Form', { exact: true }).fill('Kiss');
  await page.getByRole('button', { name: 'Eintrag hinzufügen' }).click();
  await expect.poll(() => patches.length).toBe(2);
  expect(speech).toHaveLength(0);
  await choose(page, 'Deutsche Stimme', 'Flüstern – Thorsten Emotional');
  await expectSample(page);
  expect(speech[0].voice).toBe('whisper');
  expect(speech[0].language_mode).toBe('de');
  expect(speech[0].text).toContain('Guten Tag!');
  expect(speech[0].options.speed).toBe(1.15);
  expect(speech[0].options.pronunciations[0].pronunciation).toBe('Kiss');
  expect(await page.evaluate(() => window.speechSettingsPlays[0].active)).toBe(true);
  expect(await page.evaluate(() => window.speechSettingsPlays[0].element === window.speechSettingsPlays[1].element)).toBe(true);
  await choose(page, 'Stimmenanbieter', 'Thorsten Kokoro');
  await expectSample(page, 2);
  await expect.poll(() => persisted.ui.notes_tts_options.engine).toBe('kokoro');
  expect(speech[1].options).toEqual({ ...speech[0].options, engine: 'kokoro' });
  expect(speech[1].text).toBe(speech[0].text);
  await expect(page.locator('audio')).not.toBeVisible();
  await page.getByRole('button', { name: 'Stoppen', exact: true }).click();
  await expect(page.locator('audio')).not.toHaveAttribute('src', /blob:/);
  await page.getByRole('tab', { name: 'Allgemein', exact: true }).click();
  await page.getByRole('tab', { name: 'Sprachausgabe', exact: true }).click();
  await expect(page.locator('#speech-speed')).toHaveValue('1.15');
  await page.getByText('Eigenes Aussprachewörterbuch').click();
  await expect(page.locator('.speech-entry')).toContainText('QIS');
  expect(speech).toHaveLength(2); // Reopening does not read the text again.
});

test('reselecting the current voice reads the standard text once', async ({ page }) => {
  const { speech } = await mount(page, { full: false });
  await choose(page, 'Deutsche Stimme', 'Sanft – Thorsten Emotional');
  await expectSample(page);
  expect(speech).toHaveLength(1);
  expect(speech[0].voice).toBe('neutral');
});

test('a browser playback block offers a retry without regenerating the text', async ({ page }) => {
  const { speech } = await mount(page, { full: false, block: true });
  await choose(page, 'Deutsche Stimme', 'Klar – Thorsten High');
  await expect(page.getByRole('button', { name: 'Stimme anhören', exact: true })).toBeVisible();
  await expect(page.locator('.speech-error[role="alert"]')).toContainText('Bitte klicke');
  await page.evaluate(() => {
    HTMLMediaElement.prototype.play = function() {
      window.speechSettingsPlays.push({ element: this, src: this.src, active: navigator.userActivation.isActive });
      return Promise.resolve();
    };
  });
  await page.getByRole('button', { name: 'Stimme anhören', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Stimme anhören', exact: true })).toHaveCount(0);
  await expect(page.locator('.speech-error[role="alert"]')).toHaveCount(0);
  expect(speech).toHaveLength(1);
  expect(await page.evaluate(() => window.speechSettingsPlays.at(-1).active)).toBe(true);
});

test('a new selection supersedes an older pending response', async ({ page }) => {
  const { speech, releaseSpeech } = await mount(page, { full: false, deferSpeech: true });
  await choose(page, 'Deutsche Stimme', 'Klar – Thorsten High');
  await expect.poll(() => speech.length).toBe(1);
  await choose(page, 'Deutsche Stimme', 'Heiter – Thorsten Emotional');
  await expect.poll(() => speech.length).toBe(2);
  releaseSpeech(1);
  await expectSample(page);
  releaseSpeech(0);
  await page.waitForTimeout(200);
  await expectSample(page);
  expect(speech[1].voice).toBe('amused');
  await page.getByRole('button', { name: 'Stoppen', exact: true }).click();
  await expect(page.locator('audio')).not.toHaveAttribute('src', /blob:/);
});

test('failed preference saves restore the old settings and cancel the sample', async ({ page }) => {
  await mount(page, { failedSave: true });
  await page.locator('#speech-speed').fill('1.2');
  await page.locator('#speech-speed').dispatchEvent('change');
  await expect(page.locator('#speech-speed')).toHaveValue('1');
  await choose(page, 'Deutsche Stimme', 'Klar – Thorsten High');
  await expect(page.getByRole('combobox', { name: 'Deutsche Stimme', exact: true })).toHaveValue('Sanft – Thorsten Emotional');
  await page.waitForTimeout(200);
  await expect(page.locator('audio')).not.toHaveAttribute('src', /blob:/);
  await expect(page.getByRole('button', { name: 'Stoppen', exact: true })).toHaveCount(0);
});

test('selecting the English voice reads an English standard text', async ({ page }) => {
  const { speech } = await mount(page, { full: false });
  await choose(page, 'Sprachmodus', 'Nur Englisch – Ryan High');
  await expectSample(page);
  expect(speech[0].language_mode).toBe('en');
  expect(speech[0].text).toContain('Hello!');
  await expect(page.getByRole('combobox', { name: 'Deutsche Stimme', exact: true })).toHaveCount(0);
  await expect(page.getByRole('combobox', { name: 'Stimmenanbieter', exact: true })).toHaveCount(0);
});

test('selecting a voice decodes and plays a real WAV after the delayed request', async ({ page }) => {
  await mount(page, { full: false, realAudio: true, piperOnly: true });
  await expect(page.getByRole('combobox', { name: 'Stimmenanbieter', exact: true })).toHaveCount(0);
  await choose(page, 'Deutsche Stimme', 'Klar – Thorsten High');
  await expect.poll(() => page.locator('audio').evaluate(audio => audio.readyState)).toBeGreaterThanOrEqual(2);
  await expect.poll(() => page.locator('audio').evaluate(audio => audio.paused)).toBe(false);
  await expect(page.locator('.speech-error[role="alert"]')).toHaveCount(0);
});

test('dictionary edit, toggle and deletion remain usable on a narrow dark panel', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const { patches } = await mount(page, { full: false, dark: true, initial: { notes_tts_options: {
    ...defaultSpeechOptions(), pronunciations: [{ word: 'QIS', pronunciation: 'Kiss', case_sensitive: false, enabled: true }],
  } } });
  await page.getByText('Eigenes Aussprachewörterbuch').click();
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
