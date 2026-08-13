import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveDossierConnectionPath } from '../src/utils/dossierConnections.js';

test('connection leaves horizontal card edges when cards sit beside each other', () => {
  const path = resolveDossierConnectionPath(
    { x: 20, y: 30, w: 180, h: 280 },
    { x: 300, y: 80, w: 180, h: 120 },
  );

  assert.match(path, /^M 200 170 C /);
  assert.match(path, /, 300 140$/);
});

test('connection leaves vertical card edges when the attachment sits below', () => {
  const path = resolveDossierConnectionPath(
    { x: 20, y: 20, w: 180, h: 280 },
    { x: 40, y: 400, w: 180, h: 100 },
  );

  assert.match(path, /^M 110 300 C /);
  assert.match(path, /, 130 400$/);
});

test('connection path stays empty without both cards', () => {
  assert.equal(resolveDossierConnectionPath(null, { x: 0, y: 0, w: 10, h: 10 }), '');
});
