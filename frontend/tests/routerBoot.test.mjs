import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const routerSource = await readFile(
  new URL('../src/router/index.js', import.meta.url),
  'utf8',
);
const appRootSource = await readFile(
  new URL('../src/AppRoot.vue', import.meta.url),
  'utf8',
);

test('initial application routes are statically bundled', () => {
  assert.match(routerSource, /import LoginView from/);
  assert.match(routerSource, /import AppLayout from/);
  assert.match(routerSource, /import DocumentsView from/);
  assert.doesNotMatch(routerSource, /component:\s*\(\)\s*=>\s*import\(/);
});

test('the authenticated workspace is deferred until after router boot', async () => {
  const viewSource = await readFile(
    new URL('../src/views/DocumentsView.vue', import.meta.url),
    'utf8',
  );

  assert.match(viewSource, /defineAsyncComponent\(\(\) => import\('\.\/DocumentsWorkspace\.vue'\)\)/);
  assert.match(viewSource, /<Suspense>/);
});

test('session loss redirects only protected routes and leaves the public notes harness usable', () => {
  assert.match(routerSource, /path: '\/dev\/notes'[\s\S]*?meta: \{ public: true \}/);
  assert.match(appRootSource, /router\.currentRoute\.value\.meta\.requiresAuth/);
  assert.doesNotMatch(appRootSource, /currentRoute\.value\.name !== 'login'/);
});
