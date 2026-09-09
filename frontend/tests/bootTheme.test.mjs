import test from 'node:test';
import assert from 'node:assert/strict';
import { readBootTheme, rememberBootTheme } from '../src/utils/bootTheme.js';

for (const saved of ['light', 'dark', 'system', 'invalid', null]) {
  test(`boot theme respects preference ${saved}`, t => {
    const previous = globalThis.window;
    t.after(() => { globalThis.window = previous; });
    for (const systemDark of [false, true]) {
      globalThis.window = { localStorage: { getItem: () => saved }, matchMedia: () => ({ matches: systemDark }) };
      assert.equal(readBootTheme(), ['light', 'dark'].includes(saved) ? saved : systemDark ? 'dark' : 'light');
    }
  });
}

test('unavailable storage does not block startup or theme changes', t => {
  const previous = globalThis.window;
  t.after(() => { globalThis.window = previous; });
  globalThis.window = { get localStorage() { throw new Error('Blocked'); }, matchMedia: () => ({ matches: true }) };
  assert.equal(readBootTheme(), 'dark');
  assert.doesNotThrow(() => rememberBootTheme('light'));
});

test('remembered system preference follows a changed system theme on refresh', t => {
  const previous = globalThis.window;
  t.after(() => { globalThis.window = previous; });
  let saved = 'dark';
  globalThis.window = { localStorage: { getItem: () => saved, setItem: (_, value) => { saved = value; } }, matchMedia: () => ({ matches: false }) };
  rememberBootTheme('system');
  assert.equal(readBootTheme(), 'light');
});
