import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const vuetifySource = await readFile(new URL('../src/plugins/vuetify.js', import.meta.url), 'utf8');

test('light and dark themes define surface variant colors explicitly', () => {
  assert.equal((vuetifySource.match(/'on-surface-variant':/g) || []).length, 2);
  assert.equal((vuetifySource.match(/'surface-variant':/g) || []).length, 2);
  assert.match(vuetifySource, /'on-surface-variant': paperMindLight\.textMuted/);
  assert.match(vuetifySource, /'on-surface-variant': paperMindDark\.textMuted/);
});
