import assert from 'node:assert/strict';
import test from 'node:test';

import { alignDossierRects, dossierSelectionIds } from '../src/utils/dossierSelection.js';

test('selection rectangle returns every intersecting card', () => {
  const ids = dossierSelectionIds(
    { x1: 210, y1: 180, x2: 10, y2: 10 },
    [
      { id: 'a', x: 20, y: 20, w: 100, h: 100 },
      { id: 'b', x: 160, y: 100, w: 100, h: 100 },
      { id: 'c', x: 300, y: 300, w: 100, h: 100 },
    ],
  );

  assert.deepEqual(ids, ['a', 'b']);
});

test('alignment preserves card sizes and aligns requested edges', () => {
  const cards = [
    { id: 'a', x: 20, y: 40, w: 180, h: 290 },
    { id: 'b', x: 260, y: 120, w: 180, h: 100 },
  ];

  assert.deepEqual(alignDossierRects(cards, 'left'), [
    { id: 'a', x: 20, y: 40 },
    { id: 'b', x: 20, y: 120 },
  ]);
  assert.deepEqual(alignDossierRects(cards, 'bottom'), [
    { id: 'a', x: 20, y: 40 },
    { id: 'b', x: 260, y: 230 },
  ]);
});
