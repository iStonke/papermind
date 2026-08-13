import assert from 'node:assert/strict';
import test from 'node:test';

import { arrangeDossierRects } from '../src/utils/dossierArrange.js';

test('tidy layout keeps the visible reading order and aligns cards to rows', () => {
  const placements = arrangeDossierRects([
    { id: 'b', x: 250, y: 20, w: 184, h: 96, sortOrder: 2 },
    { id: 'c', x: 20, y: 220, w: 184, h: 124, sortOrder: 3 },
    { id: 'a', x: 20, y: 20, w: 184, h: 292, sortOrder: 1 },
  ], { columns: 2, grid: 26, startX: 26, startY: 26, gap: 20 });

  assert.deepEqual(placements, [
    { id: 'a', x: 26, y: 26 },
    { id: 'b', x: 234, y: 26 },
    { id: 'c', x: 26, y: 338 },
  ]);
});

test('tidy layout creates non-overlapping grid-aligned columns', () => {
  const placements = arrangeDossierRects([
    { id: 'a', x: 0, y: 0, w: 184, h: 124, sortOrder: 1 },
    { id: 'b', x: 0, y: 0, w: 184, h: 124, sortOrder: 2 },
  ], { columns: 2, grid: 26 });

  assert.equal(placements[1].x - placements[0].x, 208);
  assert.equal(placements[0].x % 26, 0);
  assert.equal(placements[1].x % 26, 0);
});

test('tidy layout returns no placements for an empty board', () => {
  assert.deepEqual(arrangeDossierRects([]), []);
});
