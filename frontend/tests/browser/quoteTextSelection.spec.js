import { expect, test } from '@playwright/test';
test('quote allows native text selection and copies only selected text', async ({ page }) => {
  await page.route('**/__quote-selection', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app"></div></body></html>' }));
  await page.goto('/__quote-selection');
  await page.evaluate(async () => { (await import('/tests/browser/fixtures/quoteTextSelection.js')).mountQuoteSelection(); });
  const quote = page.locator('.pm-ocrquote__text');
  await expect(quote).toBeVisible();
  await quote.click();
  expect(await page.evaluate(() => window.getSelection().toString())).toBe('');
  await expect(page.locator('.pm-ocrquote')).not.toHaveClass(/is-selected|ProseMirror-selectednode/);
  await quote.click({ clickCount: 3 });
  expect(await page.evaluate(() => window.getSelection().toString())).toContain('Dieser');
  expect(await quote.evaluate(el => el.isContentEditable)).toBe(false);
  const copied = await quote.evaluate(el => {
    const range = document.createRange();
    range.selectNodeContents(el);
    const selection = window.getSelection();
    selection.removeAllRanges(); selection.addRange(range);
    const data = new DataTransfer();
    el.dispatchEvent(new ClipboardEvent('copy', { bubbles: true, cancelable: true, clipboardData: data }));
    return data.getData('text/plain');
  });
  expect(copied).toBe('Dieser Text ist auswählbar und kopierbar.');
  await page.getByRole('button', { name: 'Eigene Notiz hinzufügen' }).click();
  const ownNote = page.getByRole('textbox', { name: 'Eigene Notiz' });
  await expect(ownNote).toBeFocused();
  const appearance = await ownNote.evaluate(el => {
    const section = el.closest('.pm-ocrquote__annotation');
    const box = section.closest('.pm-ocrquote');
    return {
      inputBackground: getComputedStyle(el).backgroundColor,
      inputBorder: getComputedStyle(el).borderTopWidth,
      attached: Math.abs(section.getBoundingClientRect().bottom - box.getBoundingClientRect().bottom) < 1,
      distinctBackground: getComputedStyle(section).backgroundColor !== getComputedStyle(box).backgroundColor,
    };
  });
  expect(appearance).toEqual({ inputBackground: 'rgba(0, 0, 0, 0)', inputBorder: '0px', attached: true, distinctBackground: true });
  const darkBackground = await ownNote.evaluate(el => {
    const box = el.closest('.pm-ocrquote');
    box.style.setProperty('--pm-viewer-surface', '#1b2528');
    box.style.setProperty('--pm-content-surface', '#263134');
    const section = el.closest('.pm-ocrquote__annotation');
    const color = getComputedStyle(section).backgroundColor;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, 1, 1);
    const rgb = [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
    box.style.removeProperty('--pm-viewer-surface');
    box.style.removeProperty('--pm-content-surface');
    return rgb;
  });
  expect(Math.max(...darkBackground)).toBeLessThan(60);
  const initialHeight = await ownNote.evaluate(el => el.clientHeight);
  await ownNote.fill(Array(12).fill('Zusätzliche Gedanken').join('\n'));
  expect(await ownNote.evaluate(el => el.clientHeight)).toBeGreaterThan(initialHeight * 5);
  expect(await ownNote.evaluate(el => el.scrollHeight <= el.clientHeight && getComputedStyle(el).overflowY === 'hidden')).toBe(true);
  await page.getByRole('button', { name: 'Eigene Notiz', exact: true }).click();
  await expect(ownNote).toHaveCount(0);
  const animationSize = await page.evaluate(async () => {
    document.querySelector('.pm-ocrquote__annotation-toggle').click();
    await Promise.resolve();
    const input = document.querySelector('.pm-ocrquote__annotation-input');
    const panel = input.parentElement;
    const animation = panel.getAnimations()[0];
    const target = parseFloat(animation.effect.getKeyframes().at(-1).height);
    const fullHeight = panel.scrollHeight;
    await animation.finished;
    return { target, fullHeight, finalHeight: panel.getBoundingClientRect().height };
  });
  expect(animationSize.target).toBe(animationSize.fullHeight);
  expect(Math.abs(animationSize.finalHeight - animationSize.target)).toBeLessThan(1);
  await ownNote.fill('Kurz');
  expect(await ownNote.evaluate(el => el.clientHeight)).toBe(initialHeight);
  await ownNote.fill('Mein Beispiel\nEine offene Frage');
  expect(await page.evaluate(() => window.quoteTestEditor.getJSON().content[0].attrs.ownNote)).toBe('Mein Beispiel\nEine offene Frage');
  await page.getByRole('button', { name: 'Eigene Notiz', exact: true }).click();
  await expect(ownNote).toHaveCount(0);
  await expect(page.locator('.pm-ocrquote__annotation-preview')).toContainText('Mein Beispiel');
  // Gespeicherte Attribute überleben das erneute Laden der Notiz.
  await page.evaluate(() => {
    const saved = window.quoteTestEditor.getJSON();
    window.quoteTestEditor.commands.setContent(saved);
  });
  await page.locator('.pm-ocrquote__annotation-toggle').click();
  await expect(ownNote).toHaveValue('Mein Beispiel\nEine offene Frage');
  const roundTrip = await page.evaluate(() => {
    const html = window.quoteTestEditor.getHTML();
    window.quoteTestEditor.commands.setContent(html);
    return window.quoteTestEditor.getJSON().content[0].attrs.ownNote;
  });
  expect(roundTrip).toBe('Mein Beispiel\nEine offene Frage');
  await page.getByRole('button', { name: 'Box und Markierung entfernen' }).click();
  await expect(page.locator('.pm-ocrquote')).toHaveCount(0);
});

test('empty first line before a quote can be removed without deleting the quote', async ({ page }) => {
  await page.route('**/__quote-selection', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app"></div></body></html>' }));
  await page.goto('/__quote-selection');
  await page.evaluate(async () => { (await import('/tests/browser/fixtures/quoteTextSelection.js')).mountQuoteSelection(); });
  for (const key of ['Backspace', 'Delete']) {
    await page.evaluate(() => {
      const editor = window.quoteTestEditor;
      editor.commands.setContent({ type: 'doc', content: [
        { type: 'paragraph' },
        { type: 'ocrQuote', attrs: { text: 'Zitat bleibt erhalten.', ownNote: 'Meine Gedanken' } },
        { type: 'paragraph' },
      ] });
      editor.commands.setTextSelection(1);
      editor.view.focus();
    });
    await page.keyboard.press(key);
    expect(await page.evaluate(() => window.quoteTestEditor.getJSON().content[0])).toMatchObject({
      type: 'ocrQuote', attrs: { text: 'Zitat bleibt erhalten.', ownNote: 'Meine Gedanken' },
    });
    await expect(page.locator('.pm-ocrquote')).toHaveCount(1);
  }
});

test('empty lines are removable between and after boxes and inside containers', async ({ page }) => {
  await page.route('**/__quote-selection', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app"></div></body></html>' }));
  await page.goto('/__quote-selection');
  await page.evaluate(async () => { (await import('/tests/browser/fixtures/quoteTextSelection.js')).mountQuoteSelection(); });
  const scenarios = ['between', 'after', 'text', 'nested', 'required'];
  for (const scenario of scenarios) {
    for (const key of ['Backspace', 'Delete']) {
      await page.evaluate(scenario => {
        const q = { type: 'ocrQuote', attrs: { text: 'Erhalten' } };
        const p = { type: 'paragraph' };
        const text = { type: 'paragraph', content: [{ type: 'text', text: 'Text bleibt' }] };
        const content = scenario === 'between' ? [q, p, q]
          : scenario === 'after' ? [q, p]
          : scenario === 'text' ? [text, p, text]
          : scenario === 'nested' ? [{ type: 'blockquote', content: [p, q] }]
          : [{ type: 'bulletList', content: [{ type: 'listItem', content: [p, q] }] }];
        const editor = window.quoteTestEditor;
        editor.commands.setContent({ type: 'doc', content });
        let pos;
        editor.state.doc.descendants((node, at) => {
          if (pos === undefined && node.type.name === 'paragraph' && !node.content.size) pos = at + 1;
        });
        editor.commands.setTextSelection(pos);
        editor.view.focus();
        window.emptyLineBefore = editor.state.doc.toJSON();
      }, scenario);
      await page.keyboard.press(key);
      const result = await page.evaluate(() => {
        const doc = window.quoteTestEditor.state.doc;
        let emptyCount = 0;
        doc.descendants(node => { if (node.type.name === 'paragraph' && !node.content.size) emptyCount++; });
        doc.check();
        return { emptyCount, json: doc.toJSON(), before: window.emptyLineBefore };
      });
      if (scenario === 'required') expect(result.json).toEqual(result.before);
      else expect(result.emptyCount).toBe(0);
      await expect(page.getByText('Erhalten', { exact: true })).toHaveCount(scenario === 'between' ? 2 : scenario === 'text' ? 0 : 1);
    }
  }
});
