import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(
  new URL('../src/views/LoginView.vue', import.meta.url),
  'utf8',
);

test('login errors use a compact, quiet presentation while remaining accessible', () => {
  assert.match(source, /class="mb-3 login-alert"/);
  assert.match(source, /role="alert"/);
  assert.match(source, /aria-live="assertive"/);
  assert.match(source, /size="19"/);
  assert.match(source, /\.login-alert\s*\{[^}]*padding: 9px 11px;/s);
  assert.match(source, /\.login-alert__title\s*\{[^}]*font-size: 0\.84rem;/s);
  assert.match(source, /\.login-alert__text\s*\{[^}]*font-size: 0\.78rem;/s);
  assert.doesNotMatch(source, /<v-alert\s+v-if="error"/);
});

test('login fields are compact and replace the browser autofill yellow', () => {
  assert.equal((source.match(/density="compact"/g) || []).length, 5);
  assert.equal((source.match(/login-field/g) || []).length >= 5, true);
  assert.match(source, /input:-webkit-autofill/);
  assert.match(source, /input:autofill/);
  assert.match(source, /\.login-field :deep\(\.v-field__input\)[\s\S]*?min-height: 40px;/);
  assert.match(source, /--login-field-fill: #082a36/);
  assert.match(source, /\.login-field :deep\(\.v-field\)[\s\S]*?background: var\(--login-field-fill\)/);
  assert.match(source, /box-shadow: inset 0 0 0 1000px var\(--login-field-fill\)/);
  assert.match(source, /:has\(input:-webkit-autofill\).*?v-field-label--floating/s);
});
