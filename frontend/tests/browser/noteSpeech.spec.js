import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const productionCsp = readFileSync(new URL('../../nginx.conf', import.meta.url), 'utf8')
  .match(/add_header Content-Security-Policy "([^"]+)"/)[1];

async function mount(page, { blockPlayback = false, deferPlayback = false, realAudio = false, csp = false, paragraphs } = {}) {
  const requests = [];
  // A valid one-second mono PCM WAV, so the real media decoder can be tested.
  const wav = Buffer.alloc(44 + 16000);
  wav.write('RIFF'); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8);
  wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(8000, 24); wav.writeUInt32LE(16000, 28);
  wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34);
  wav.write('data', 36); wav.writeUInt32LE(16000, 40);
  await page.route('**/api/tts/speech', async route => {
    requests.push(route.request().postDataJSON());
    // Deliberately break the synchronous click context, as Piper does.
    await new Promise(resolve => setTimeout(resolve, 150));
    await route.fulfill({ contentType: 'audio/wav', body: wav });
  });
  await page.route('**/__note-speech', route => route.fulfill({
    contentType: 'text/html',
    headers: csp ? { 'Content-Security-Policy': productionCsp } : {},
    body: '<div id="app" class="papermind-app v-theme--light" style="height:800px"></div>',
  }));
  await page.goto('/__note-speech');
  await page.evaluate(async ({ blockPlayback, deferPlayback, realAudio, paragraphs }) => {
    window.speechPlays = [];
    window.speechRevokedUrls = [];
    window.speechMediaViolations = [];
    document.addEventListener('securitypolicyviolation', event => {
      if (event.effectiveDirective === 'media-src') window.speechMediaViolations.push(event.blockedURI);
    });
    const revoke = URL.revokeObjectURL;
    URL.revokeObjectURL = url => { window.speechRevokedUrls.push(url); revoke(url); };
    if (!realAudio) {
      HTMLMediaElement.prototype.play = function () {
        window.speechPlays.push({ audio: this, src: this.src, active: navigator.userActivation.isActive });
        if (this.src.startsWith('data:')) return Promise.resolve();
        if (deferPlayback) return new Promise(resolve => { window.finishSpeechPlay = resolve; });
        if (blockPlayback) return Promise.reject(new DOMException('Browser denied playback', 'NotAllowedError'));
        return Promise.resolve();
      };
    }
    (await import('/tests/browser/fixtures/noteSpeech.js')).mountSpeechEditor({ paragraphs });
  }, { blockPlayback, deferPlayback, realAudio, paragraphs });
  await expect(page.locator('.tiptap')).toContainText('Dieser Text wird vorgelesen.');
  await page.locator('.tiptap').evaluate(el => el.editor.commands.setTextSelection({ from: 1, to: el.editor.state.doc.content.size - 1 }));
  await expect(page.getByRole('button', { name: 'Markierten Text vorlesen', exact: true })).toBeVisible();
  return requests;
}

test('primes the same audio element during the click and preserves pause/resume', async ({ page }) => {
  const requests = await mount(page);
  await page.getByRole('button', { name: 'Markierten Text vorlesen', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Vorlesen pausieren', exact: true })).toBeVisible();
  expect(await page.evaluate(() => ({
    primedDuringClick: window.speechPlays[0].active,
    reused: window.speechPlays[0].audio === window.speechPlays[1].audio,
    sources: window.speechPlays.map(p => p.src.split(':')[0]),
  }))).toEqual({ primedDuringClick: true, reused: true, sources: ['data', 'blob'] });
  await page.getByRole('button', { name: 'Vorlesen pausieren', exact: true }).click();
  await page.getByRole('button', { name: 'Vorlesen fortsetzen', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Vorlesen pausieren', exact: true })).toBeVisible();
  expect(requests).toEqual([{ text: 'Dieser Text wird vorgelesen.', voice: 'standard', language_mode: 'auto' }]);
  await page.evaluate(() => window.unmountSpeechEditor());
  expect(await page.evaluate(() => window.speechRevokedUrls.length)).toBe(1);
});

test('selection speech keeps paragraph boundaries for natural pauses', async ({ page }) => {
  const paragraphs = ['Dieser Text wird vorgelesen.', 'Absatz zwei bleibt getrennt.'];
  const requests = await mount(page, { paragraphs });
  await page.getByRole('button', { name: 'Markierten Text vorlesen', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Vorlesen pausieren', exact: true })).toBeVisible();
  expect(requests[0].text).toBe(paragraphs.join('\n'));
});

test('a blocked clip can be started by another click or Enter without regenerating it', async ({ page }) => {
  const requests = await mount(page, { blockPlayback: true });
  await page.getByRole('button', { name: 'Markierten Text vorlesen', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('Audio ist bereit. Bitte auf „Vorlesen starten“ klicken.');
  const start = page.getByRole('button', { name: 'Vorlesen starten', exact: true });
  await start.click();
  await expect(start).toBeVisible();
  await page.evaluate(() => {
    HTMLMediaElement.prototype.play = function () { window.speechPlays.push({ audio: this, active: navigator.userActivation.isActive }); return Promise.resolve(); };
  });
  await start.focus();
  await start.press('Enter');
  await expect(page.getByRole('button', { name: 'Vorlesen pausieren', exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(requests).toHaveLength(1);
  expect(await page.evaluate(() => window.speechPlays.at(-1).active)).toBe(true);
});

test('changing the selection during pending playback ignores a late resolution', async ({ page }) => {
  await mount(page, { deferPlayback: true });
  await page.getByRole('button', { name: 'Markierten Text vorlesen', exact: true }).click();
  await expect.poll(() => page.evaluate(() => typeof window.finishSpeechPlay)).toBe('function');
  await page.locator('.tiptap').evaluate(el => el.editor.commands.setTextSelection({ from: 1, to: 6 }));
  await page.evaluate(() => window.finishSpeechPlay());
  await expect(page.getByRole('button', { name: 'Markierten Text vorlesen', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.speechRevokedUrls.length)).toBe(1);
});

test('real WAV playback works under the production CSP after delayed synthesis', async ({ page }) => {
  await mount(page, { realAudio: true, csp: true });
  await page.getByRole('button', { name: 'Markierten Text vorlesen', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Vorlesen pausieren', exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Markierten Text vorlesen', exact: true })).toBeVisible();
  expect(await page.evaluate(() => window.speechMediaViolations)).toEqual([]);
});
