import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const vuetifySource = await readFile(new URL('../src/plugins/vuetify.js', import.meta.url), 'utf8');
const themeSource = await readFile(new URL('../src/theme/theme.css', import.meta.url), 'utf8');

test('theme tokens preserve sidebar inheritance while covering teleported overlays', () => {
  // Vuetify repeats these classes on fields/lists inside the always-dark sidebar.
  // Bare theme selectors would reset their inherited text to light-mode black.
  assert.doesNotMatch(themeSource, /^\s*\.v-theme--(?:light|dark)\s*[,\{]/m);
  for (const mode of ['light', 'dark']) {
    assert.ok(themeSource.includes(`.papermind-app.v-theme--${mode},`));
    assert.ok(themeSource.includes(`.v-overlay-container > .v-overlay.v-theme--${mode},`));
    assert.ok(themeSource.includes(`.pm-shortcuts-overlay.v-theme--${mode} {`));
  }
});

test('light and dark themes define surface variant colors explicitly', () => {
  assert.equal((vuetifySource.match(/'on-surface-variant':/g) || []).length, 2);
  assert.equal((vuetifySource.match(/'surface-variant':/g) || []).length, 2);
  assert.match(vuetifySource, /'on-surface-variant': paperMindLight\.textMuted/);
  assert.match(vuetifySource, /'on-surface-variant': paperMindDark\.textMuted/);
});
