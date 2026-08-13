import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveDossierSmartGuides } from '../src/utils/dossierSmartGuides.js';

test('smart guides snap matching edges inside the threshold', () => {
  const guides = resolveDossierSmartGuides(
    { x: 104, y: 70, w: 80, h: 100 },
    [{ x: 100, y: 220, w: 80, h: 100 }],
  );

  assert.equal(guides.x.kind, 'start');
  assert.equal(guides.x.delta, -4);
  assert.equal(guides.x.coordinate, 100);
  assert.equal(guides.y, null);
});

test('smart guides choose the nearest candidate independently on both axes', () => {
  const guides = resolveDossierSmartGuides(
    { x: 198, y: 203, w: 100, h: 80 },
    [
      { x: 200, y: 20, w: 100, h: 80 },
      { x: 20, y: 200, w: 100, h: 80 },
    ],
  );

  assert.equal(guides.x.delta, 2);
  assert.equal(guides.y.delta, -3);
  assert.ok(guides.x.to > guides.x.from);
  assert.ok(guides.y.to > guides.y.from);
});

test('smart guides place one outer edge directly against the opposite edge', () => {
  const guides = resolveDossierSmartGuides(
    { x: 185, y: 20, w: 80, h: 80 },
    [{ x: 100, y: 160, w: 80, h: 80 }],
  );

  assert.equal(guides.x.kind, 'start-end');
  assert.equal(guides.x.coordinate, 180);
  assert.equal(guides.x.delta, -5);
});

test('smart guides stay inactive outside the magnetic range', () => {
  assert.deepEqual(
    resolveDossierSmartGuides(
      { x: 20, y: 20, w: 80, h: 80 },
      [{ x: 120, y: 120, w: 80, h: 80 }],
      7,
    ),
    { x: null, y: null },
  );
});
