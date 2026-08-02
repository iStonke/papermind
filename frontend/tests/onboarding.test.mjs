import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const componentSource = await readFile(
  new URL('../src/components/OnboardingDialog.vue', import.meta.url),
  'utf8',
);
const layoutSource = await readFile(
  new URL('../src/views/AppLayout.vue', import.meta.url),
  'utf8',
);
const loginSource = await readFile(
  new URL('../src/views/LoginView.vue', import.meta.url),
  'utf8',
);
const settingsSource = await readFile(
  new URL('../src/components/SettingsDialog.vue', import.meta.url),
  'utf8',
);

test('onboarding is announced after registration and can start imports', () => {
  assert.match(loginSource, /pm\.onboarding\.after-register/);
  assert.match(layoutSource, /ui\.requestAction\('import'\)/);
  assert.match(layoutSource, /completeOnboarding\(true\)/);
});

test('development builds expose a manual onboarding launcher', () => {
  assert.match(layoutSource, /import\.meta\.env\.DEV/);
  assert.match(layoutSource, /DEV · Onboarding/);
  assert.match(layoutSource, /ui\.openOnboarding\('dev'\)/);
});

test('settings can reopen onboarding without stacking dialogs', () => {
  assert.match(settingsSource, /Onboarding anzeigen/);
  assert.match(settingsSource, /emit\('show-onboarding'\)/);
  assert.match(layoutSource, /ui\.closeSettings\(\)/);
  assert.match(layoutSource, /ui\.openOnboarding\('settings'\)/);
});

test('onboarding respects reduced-motion preferences', () => {
  assert.match(componentSource, /prefers-reduced-motion:\s*reduce/);
  assert.match(componentSource, /animation-duration:\s*0\.001ms/);
});
