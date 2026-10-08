import { expect, test } from '@playwright/test';
test('long filename stays on one line with its complete tooltip', async ({ page }) => {
  await page.route('**/__filename', route => route.fulfill({ contentType: 'text/html', body: '<html><body><div id="app"></div></body></html>' }));
  await page.goto('/__filename');
  await page.evaluate(async () => {
    const { default: source } = await import('/src/components/notes/NoteWorkspaceEditor.vue?raw');
    const css = source.match(/\.note-workspace-editor__document-filename \{[\s\S]*?text-overflow: ellipsis;\n\}/)[0];
    const style = document.createElement('style');
    style.textContent = css.replace(/:deep\(([^)]+)\)/g, '$1');
    document.head.append(style);
    const name = '8764_Steinke_Jan_ISTQB__Certified_Tester_-_Foundation_Level_v4.0__CTFL___DE__2026-09-14';
    document.querySelector('#app').innerHTML = `<div style="width:240px"><span class="note-workspace-editor__document-filename" title="${name}">${name}</span></div>`;
  });
  const name = page.locator('.note-workspace-editor__document-filename');
  await expect(name).toHaveCSS('white-space', 'nowrap');
  await expect(name).toHaveCSS('text-overflow', 'ellipsis');
  expect(await name.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true);
  expect(await name.evaluate(el => el.getBoundingClientRect().height <= parseFloat(getComputedStyle(el).lineHeight) + 1)).toBe(true);
  expect(await name.getAttribute('title')).toBe(await name.textContent());
});
