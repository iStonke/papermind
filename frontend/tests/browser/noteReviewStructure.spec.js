import { expect, test } from '@playwright/test';

test('previews and applies table and callout transformations with real editor nodes and undo', async ({ page }) => {
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.route('**/__review-structure',r=>r.fulfill({contentType:'text/html',body:'<html><body><div id="app" class="papermind-app v-theme--light"></div></body></html>'}));
  await page.goto('/__review-structure');
  await page.evaluate(async()=>{const {mountStructureReview}=await import('/tests/browser/fixtures/reviewStructure.js');mountStructureReview();});
  await expect(page.locator('.pm-review-card')).toHaveCount(2);
  await expect(page.locator('.pm-review-preview')).toHaveCount(0);
  await page.locator('.pm-review-card[data-review-id="1"]').click();
  await page.getByRole('button', {name:'Vorschau',exact:true}).click();
  await expect(page.locator('.pm-review-preview table')).toBeVisible();
  await page.getByRole('button', {name:'Vorschau',exact:true}).click();
  await expect(page.locator('.pm-review-preview')).toHaveCount(0);
  await page.locator('.pm-review-card[data-review-id="2"]').click();
  await page.getByRole('button', {name:'Vorschau',exact:true}).click();
  await expect(page.locator('.pm-review-preview aside[data-callout="important"]')).toBeVisible();
  expect(await page.evaluate(()=>window.structurePayload.note_structure.length)).toBe(5);
  await page.locator('.pm-review-card[data-review-id="1"]').click();
  await page.locator('.pm-review-card.is-focus').getByRole('button',{name:'Annehmen',exact:true}).click();
  await expect(page.locator('.tiptap table')).toBeVisible();
  await page.locator('.pm-review-card[data-review-id="2"]').click();
  await page.locator('.pm-review-card.is-focus').getByRole('button',{name:'Annehmen',exact:true}).click();
  await expect(page.locator('.tiptap .pm-callout')).toContainText('Vor dem Speichern prüfen.');
  expect(await page.evaluate(()=>window.structureReview.editor.state.doc.firstChild.textContent)).toBe('Davor');
  expect(await page.evaluate(()=>window.structureReview.editor.state.doc.lastChild.textContent)).toBe('Danach');
  await page.evaluate(()=>{const {editor,c}=window.structureReview;c.closeReview();editor.commands.undo();editor.commands.undo();});
  expect(await page.evaluate(()=>window.structureReview.editor.getJSON())).toEqual(await page.evaluate(()=>window.structureReview.before));
});

async function mountEditableReview(page, deferred = false) {
  await page.route('**/__review-edit', r => r.fulfill({contentType:'text/html',body:'<div id="app"></div>'}));
  await page.goto('/__review-edit');
  await page.evaluate(async deferred => {
    const {mountStructureReview} = await import('/tests/browser/fixtures/reviewStructure.js');
    mountStructureReview({deferred});
  }, deferred);
}

test('manual editing preserves unaffected suggestions and invalidates changed blocks', async ({ page }) => {
  await mountEditableReview(page);
  await expect(page.locator('.pm-review-card')).toHaveCount(2);
  await expect(page.locator('.tiptap')).toHaveAttribute('contenteditable', 'true');
  await page.locator('.tiptap > p').first().click();
  await page.keyboard.press('Home');
  await page.keyboard.type('Neu: ');
  await expect(page.locator('.pm-review-card')).toHaveCount(2);
  await expect(page.locator('.pm-review-panel__changed')).toBeVisible();
  await page.evaluate(() => {
    const {editor} = window.structureReview;
    editor.commands.insertContentAt(editor.state.doc.firstChild.nodeSize + 1, 'Andere ');
  });
  await expect(page.locator('.pm-review-card')).toHaveCount(1);
  await expect(page.locator('.pm-review-card')).toHaveAttribute('data-review-id', '2');
  await page.evaluate(async () => {
    const {c} = window.structureReview;
    c.closeReview(); await c.startReview();
  });
  await expect(page.locator('.pm-review-panel__changed')).toBeVisible();
  await page.evaluate(() => window.structureReview.c.acceptChange(2));
  await expect(page.locator('.tiptap .pm-callout')).toContainText('Vor dem Speichern prüfen.');
  await expect(page.locator('.tiptap')).toContainText('Andere Name: Anna');
});

test('editing during a request cancels it and ignores the late response', async ({ page }) => {
  await mountEditableReview(page, true);
  await page.evaluate(() => window.structureReview.editor.commands.insertContentAt(1, 'Neu '));
  expect(await page.evaluate(() => window.structureSignal.aborted)).toBe(true);
  await page.evaluate(() => window.finishStructureStream());
  await expect(page.locator('.pm-review-card')).toHaveCount(0);
  await expect(page.getByText('Text geändert', {exact:true})).toBeVisible();
  expect(await page.evaluate(() => window.structureReview.c.review.loading)).toBe(false);
});

test('rechecking validates current text and preserves existing readonly settings', async ({ page }) => {
  await mountEditableReview(page);
  await expect(page.locator('.pm-review-card')).toHaveCount(2);
  await page.evaluate(async () => {
    const {editor,c} = window.structureReview;
    editor.commands.clearContent(); await c.requestReview();
  });
  await expect(page.getByText('Diese Notiz ist leer – es gibt nichts zu überarbeiten.')).toBeVisible();
  await page.evaluate(async () => {
    const {editor,c} = window.structureReview;
    editor.commands.setContent('<p>' + 'x'.repeat(12001) + '</p>'); await c.requestReview();
  });
  await expect(page.getByText('Die Notiz ist für eine Überarbeitung in einem Schritt zu lang.')).toBeVisible();
  await page.evaluate(async () => {
    const {editor,c} = window.structureReview;
    c.closeReview(); editor.setEditable(false); await c.startReview(); c.closeReview();
  });
  await expect(page.locator('.tiptap')).toHaveAttribute('contenteditable', 'false');
});

test('placing the caret clears the selected suggestion and editor dimming without losing suggestions', async ({ page }) => {
  await mountEditableReview(page);
  const card = page.locator('.pm-review-card[data-review-id="1"]');
  await card.click();
  await expect(page.locator('.tiptap .pm-review-muted').first()).toBeAttached();
  await page.locator('.tiptap > p').first().click();
  await expect(page.locator('.tiptap .pm-review-muted')).toHaveCount(0);
  await expect(page.locator('.tiptap .is-focus')).toHaveCount(0);
  expect(await page.evaluate(() => window.structureReview.c.review.focusId)).toBeNull();
  await expect(page.locator('.pm-review-card')).toHaveCount(2);
  // Erneut dieselbe Schreibmarke anklicken: keine selectionUpdate-Abhängigkeit.
  await card.click();
  await page.locator('.tiptap > p').first().click();
  expect(await page.evaluate(() => window.structureReview.c.review.focusId)).toBeNull();
  expect(await page.evaluate(() => window.structureReview.editor.isFocused)).toBe(true);
});
