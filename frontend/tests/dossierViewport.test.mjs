import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveDossierFit } from '../src/utils/dossierViewport.js';

test('fit view centers all board elements and chooses the limiting scale', () => {
  const fit = resolveDossierFit(
    [{ x: 100, y: 50, w: 700, h: 300 }],
    { width: 500, height: 400 },
    { padding: 50, minScale: 0.25, maxScale: 1.2 },
  );

  assert.equal(fit.scale, 4 / 7);
  assert.equal(fit.x, (500 - 900 * fit.scale) / 2);
  assert.equal(fit.y, (400 - 400 * fit.scale) / 2);
});

test('fit view does not enlarge content beyond the requested scale', () => {
  const fit = resolveDossierFit(
    [{ x: 20, y: 20, w: 100, h: 100 }],
    { width: 1000, height: 700 },
    { maxScale: 1.2 },
  );

  assert.equal(fit.scale, 1.2);
});

test('fit view stays inactive without content', () => {
  assert.equal(resolveDossierFit([], { width: 1000, height: 700 }), null);
});
