import { test, expect } from '@playwright/test';

async function mount(page, options = {}) {
  await page.setViewportSize({ width: 1000, height: 950 });
  await page.route('**/__document-knowledge', route => route.fulfill({ contentType: 'text/html', body: '<div id="app"></div>' }));
  await page.goto('/__document-knowledge');
  await page.evaluate(async options => (await import('/tests/browser/fixtures/documentKnowledge.js')).mount(options), options);
}

for (const theme of ['light', 'dark']) {
  test(`knowledge shows stored results, date and open fields in ${theme}`, async ({ page }) => {
    await mount(page, { theme });
    await page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Wissen', exact: true });
    await expect(dialog.getByRole('heading', { name: 'Kurzfassung', exact: true })).toBeVisible();
    await expect(dialog).toContainText('183,50');
    await expect(dialog).toContainText('HUK-COBURG');
    await expect(dialog).toContainText('01.01.2024');
    await expect(dialog).toContainText('30.10.2026');
    await expect(dialog.getByRole('heading', { name: 'Offene Angaben', exact: true })).toBeVisible();
    await expect(dialog.getByRole('button', { name: '4 Angaben mit KI ergänzen', exact: true })).toBeVisible();
    await expect(dialog.locator('.document-knowledge__missing .document-knowledge__tags')).toHaveCount(0);
    await expect(dialog.getByRole('meter', { name: 'Vollständigkeit der Dokumentangaben' })).toHaveAttribute('aria-valuenow', '1');
    await expect(dialog.locator('.document-knowledge__status')).toHaveText('Abgeschlossen');
    const help = dialog.getByRole('button', { name: 'Was zeigt Wissen?', exact: true });
    const explanation = dialog.locator('.document-knowledge__explanation');
    await expect(help).toHaveAttribute('aria-expanded', 'false');
    await expect(explanation).toBeHidden();
    expect(await page.evaluate(() => window.knowledgeDemo.headerClicks.value)).toBe(0);
    await dialog.screenshot({ path: `/tmp/papermind-knowledge-${theme}.png`, animations: 'disabled' });
    await help.focus();
    await page.keyboard.press('Enter');
    await expect(help).toHaveAttribute('aria-expanded', 'true');
    await expect(explanation).toBeVisible();
    await expect(explanation).toContainText('welche Dokumentfelder bereits ausgefüllt sind');
    await dialog.screenshot({ path: `/tmp/papermind-knowledge-help-${theme}.png`, animations: 'disabled' });
    await help.click();
    await expect(explanation).toBeHidden();
    await help.click();
    await dialog.getByRole('button', { name: 'Wissen schließen', exact: true }).focus();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true })).toBeFocused();
    await page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true }).click();
    await expect(help).toHaveAttribute('aria-expanded', 'false');
    await expect(explanation).toBeHidden();
  });
}

test('knowledge keeps old results marked during work or failure and closes on document changes', async ({ page }) => {
  await mount(page, { document: { ai_summary: '<script>Keine Ausführung</script>' } });
  await page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Wissen', exact: true });
  await expect(dialog.getByLabel('Kurzfassung der KI-Auswertung')).toHaveText('<script>Keine Ausführung</script>');
  await expect(dialog.locator('script')).toHaveCount(0);
  await page.evaluate(() => { window.knowledgeDemo.busy.value = true; });
  await expect(dialog).toContainText('Wird ausgewertet');
  await expect(dialog).toContainText('zuletzt verfügbaren Ergebnisse');
  await expect.poll(() => dialog.locator('.document-knowledge__status').evaluate(el => getComputedStyle(el, '::before').animationName)).toMatch(/knowledge-status-pulse/);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  expect(await dialog.locator('.document-knowledge__status').evaluate(el => getComputedStyle(el, '::before').animationName)).toBe('none');
  await page.evaluate(() => { window.knowledgeDemo.busy.value = false; window.knowledgeDemo.data.ai_status = 'error'; });
  await expect(dialog).toContainText('Fehlgeschlagen');
  await expect(dialog).toContainText('zuletzt verfügbaren Ergebnisse');
  await page.evaluate(() => { window.knowledgeDemo.data.id = 'document-b'; });
  await expect(dialog).toHaveCount(0);
});

test('completeness follows edited document fields and hides the open-fields hint once complete', async ({ page }) => {
  await mount(page);
  await page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Wissen', exact: true });
  const meter = dialog.getByRole('meter', { name: 'Vollständigkeit der Dokumentangaben' });
  await expect(meter).toHaveAttribute('aria-valuenow', '1');
  await page.evaluate(() => Object.assign(window.knowledgeDemo.data, { document_date: '2024-01-01', document_type: 'Rechnung', tags: ['Versicherung'] }));
  await expect(dialog.getByRole('button', { name: 'Korrespondent mit KI ergänzen', exact: true })).toBeVisible();
  await expect(dialog.locator('.document-knowledge__missing button')).toHaveCount(1);
  await page.evaluate(() => Object.assign(window.knowledgeDemo.data, { document_date: '2024-01-01', document_type: 'Rechnung', correspondent_id: 'huk', tags: ['Versicherung'] }));
  await expect(meter).toHaveAttribute('aria-valuenow', '5');
  await expect(dialog).toContainText('5 von 5 vorhanden');
  await expect(dialog.getByRole('heading', { name: 'Offene Angaben', exact: true })).toHaveCount(0);
  await expect(dialog.locator('.document-knowledge__segment--filled')).toHaveCount(5);
  await expect(dialog.getByRole('button', { name: /mit KI ergänzen$/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true })).not.toContainText('offen');
});

test('completion keeps the popover open, prevents clicks while busy and disappears when complete', async ({ page }) => {
  await mount(page);
  const chip = page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true });
  await expect(chip).toContainText('4 offen');
  await chip.click();
  const dialog = page.getByRole('dialog', { name: 'Wissen', exact: true });
  await dialog.getByRole('button', { name: /mit KI ergänzen$/ }).click();
  expect(await page.evaluate(() => window.knowledgeDemo.completions.value)).toEqual(['document-a']);
  await expect(dialog).toBeVisible();
  await page.evaluate(() => { window.knowledgeDemo.busy.value = true; });
  const busy = dialog.getByRole('button', { name: 'Angaben werden ergänzt …', exact: true });
  await expect(busy).toBeDisabled();
  await busy.dispatchEvent('click');
  expect(await page.evaluate(() => window.knowledgeDemo.completions.value)).toHaveLength(1);
  await page.evaluate(() => Object.assign(window.knowledgeDemo.data, { document_date: '2024-01-01', document_type: 'Rechnung', correspondent_id: 'huk', tags: ['Versicherung'] }));
  await expect(busy).toBeVisible();
  await page.evaluate(() => { window.knowledgeDemo.busy.value = false; });
  await expect(dialog).toBeVisible();
  await expect(busy).toHaveCount(0);
  await expect(dialog.getByRole('meter')).toHaveAttribute('aria-valuenow', '5');
});

test('the neutral chip has the OCR hover treatment and the popovers switch cleanly on narrow screens', async ({ page }) => {
  await mount(page);
  await page.setViewportSize({ width: 390, height: 740 });
  const chip = page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true });
  await chip.hover();
  await expect.poll(() => chip.evaluate(el => getComputedStyle(el, '::before').opacity)).toBe('1');
  expect(await chip.evaluate(el => getComputedStyle(el).textDecorationLine)).toBe('none');
  await page.getByRole('button', { name: 'OCR-Details anzeigen', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Texterkennung', exact: true })).toBeVisible();
  await chip.click();
  const dialog = page.getByRole('dialog', { name: 'Wissen', exact: true });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Texterkennung', exact: true })).toHaveCount(0);
  await expect.poll(() => dialog.evaluate(el => el.getBoundingClientRect().right)).toBeLessThanOrEqual(390);
  await dialog.screenshot({ path: '/tmp/papermind-knowledge-mobile.png', animations: 'disabled' });
  await dialog.evaluate(el => { el.scrollTop = el.scrollHeight; });
  await expect(dialog.getByRole('button', { name: 'Wissen schließen', exact: true })).toBeInViewport();
  await expect(dialog.locator('.document-knowledge__explanation')).toBeHidden();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await dialog.getByRole('button', { name: 'Was zeigt Wissen?', exact: true }).click();
  await expect(dialog.locator('.document-knowledge__explanation')).toBeInViewport();
  expect(await dialog.locator('.document-knowledge__help').evaluate(el => getComputedStyle(el).transitionDuration)).toBe('0s');
  await dialog.screenshot({ path: '/tmp/papermind-knowledge-mobile-explanation.png', animations: 'disabled' });
});

for (const theme of ['light', 'dark']) {
  test(`compact knowledge expands and permits explicit corrections in ${theme}`, async ({ page }) => {
    await mount(page, { theme, document: { ai_recipient: 'Jan Steinke, Eine lange Empfängeradresse mit weiteren Angaben' } });
    await page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Wissen', exact: true });
    await expect(dialog.locator('.document-knowledge__compact-primary')).toContainText('183,50');
    await expect(dialog.locator('.document-knowledge__compact-parties')).toContainText('HUK-COBURG → Jan Steinke');
    await expect(dialog.locator('.document-knowledge__fields')).toHaveCount(0);
    await dialog.getByRole('button', { name: 'Alle Angaben', exact: true }).click();
    await expect(dialog.locator('.document-knowledge__fields')).toContainText('Eine lange Empfängeradresse mit weiteren Angaben');
    await dialog.getByRole('button', { name: 'Weniger anzeigen', exact: true }).click();
    await dialog.getByRole('button', { name: 'Angaben bearbeiten', exact: true }).click();
    const editor = dialog.getByRole('form', { name: 'Angaben korrigieren' });
    await expect(editor.getByLabel('Dokumenttyp', { exact: true })).toBeFocused();
    expect(await editor.getByLabel('Dokumentdatum', { exact: true }).evaluate(el => getComputedStyle(el).colorScheme)).toBe(theme);
    await editor.getByLabel('Betrag', { exact: true }).fill('-225,50');
    await editor.getByLabel('Empfänger', { exact: true }).fill('Korrigierter Empfänger');
    await editor.getByLabel('Korrespondent', { exact: true }).selectOption('kmtv');
    expect(await page.evaluate(() => window.knowledgeDemo.saves.value)).toHaveLength(0);
    await dialog.screenshot({ path: `/tmp/papermind-knowledge-editor-${theme}.png`, animations: 'disabled' });
    await editor.getByRole('button', { name: 'Speichern', exact: true }).click();
    await expect(editor).toHaveCount(0);
    await expect(dialog.locator('.document-knowledge__compact-primary')).toContainText('-225,50');
    await expect(dialog.locator('.document-knowledge__compact-parties')).toHaveText('KMTV → Korrigierter Empfänger');
    await expect(dialog.getByRole('button', { name: 'Angaben bearbeiten', exact: true })).toBeFocused();
    expect(await page.evaluate(() => window.knowledgeDemo.saves.value)).toEqual([{ id: 'document-a', patch: { correspondent_id: 'kmtv', recipient: 'Korrigierter Empfänger', amount: -225.5 } }]);
    expect(await page.evaluate(() => window.knowledgeDemo.data.ai_amount)).toBe(183.5);
    await dialog.screenshot({ path: `/tmp/papermind-knowledge-compact-${theme}.png`, animations: 'disabled' });
  });
}

test('cancel discards changes, validation and failed saves retain the correction draft', async ({ page }) => {
  await mount(page);
  await page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Wissen', exact: true });
  const edit = dialog.getByRole('button', { name: 'Angaben bearbeiten', exact: true });
  await edit.click();
  let editor = dialog.getByRole('form', { name: 'Angaben korrigieren' });
  await editor.getByLabel('Betrag', { exact: true }).fill('999');
  await editor.getByRole('button', { name: 'Abbrechen', exact: true }).click();
  await expect(editor).toHaveCount(0);
  expect(await page.evaluate(() => window.knowledgeDemo.saves.value)).toHaveLength(0);
  await edit.click();
  editor = dialog.getByRole('form', { name: 'Angaben korrigieren' });
  await expect(editor.getByLabel('Betrag', { exact: true })).toHaveValue('183,5');
  await editor.getByLabel('Betrag', { exact: true }).fill('12,345');
  await editor.getByRole('button', { name: 'Speichern', exact: true }).click();
  await expect(editor.getByRole('alert')).toContainText('Nachkommastellen');
  expect(await page.evaluate(() => window.knowledgeDemo.saves.value)).toHaveLength(0);
  await editor.getByLabel('Betrag', { exact: true }).fill('0');
  await page.evaluate(() => { window.knowledgeDemo.saveFailure.value = 'Speichern fehlgeschlagen. Bitte erneut versuchen.'; });
  await editor.getByRole('button', { name: 'Speichern', exact: true }).click();
  await expect(editor.getByRole('alert')).toContainText('Speichern fehlgeschlagen');
  await expect(editor.getByLabel('Betrag', { exact: true })).toHaveValue('0');
  await page.evaluate(() => { window.knowledgeDemo.saveFailure.value = ''; });
  await editor.getByRole('button', { name: 'Speichern', exact: true }).click();
  await expect(dialog.locator('.document-knowledge__compact-primary')).toContainText('0,00');
});

test('a late save cannot modify a newly selected document or its editor', async ({ page }) => {
  await mount(page);
  await page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Wissen', exact: true });
  await dialog.getByRole('button', { name: 'Angaben bearbeiten', exact: true }).click();
  await dialog.getByLabel('Betrag', { exact: true }).fill('42');
  await page.evaluate(() => { window.knowledgeDemo.saveHandler.value = () => new Promise(resolve => { window.releaseKnowledgeSave = resolve; }); });
  await dialog.getByRole('button', { name: 'Speichern', exact: true }).click();
  await expect(dialog.getByRole('button', { name: 'Wird gespeichert …', exact: true })).toBeDisabled();
  await page.evaluate(() => { window.knowledgeDemo.data.id = 'document-b'; window.knowledgeDemo.data.ai_amount = 777; });
  await expect(dialog).toHaveCount(0);
  await page.getByRole('button', { name: 'Wissen zum Dokument anzeigen', exact: true }).click();
  await dialog.getByRole('button', { name: 'Angaben bearbeiten', exact: true }).click();
  await page.evaluate(() => window.releaseKnowledgeSave());
  await expect(dialog.getByLabel('Betrag', { exact: true })).toHaveValue('777');
  await expect(dialog.getByRole('form', { name: 'Angaben korrigieren' })).toBeVisible();
});
