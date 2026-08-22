import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(
  new URL('../src/components/SettingsDialog.vue', import.meta.url),
  'utf8',
);
const navigationStart = source.indexOf('const settingsCategories = [');
const navigationEnd = source.indexOf('const settingsCategoryGroups = [', navigationStart);
const navigation = source.slice(navigationStart, navigationEnd);

test('controls is the final category in the surface settings group', () => {
  const surfaceCategories = [...navigation.matchAll(
    /value: '([^']+)'[^\n]+group: 'surface'/g,
  )].map((match) => match[1]);

  assert.deepEqual(surfaceCategories, ['appearance', 'sidebar', 'documents', 'controls']);
});
