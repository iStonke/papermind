import test from 'node:test';
import assert from 'node:assert/strict';

import { placeSelectionBubble } from '../src/utils/noteBubblePosition.js';

const bounds = {
  viewportTop: 120,
  viewportBottom: 700,
  bubbleHeight: 40,
  gap: 8,
};

test('selection bubble stays above the selection when it fits below the toolbar', () => {
  assert.deepEqual(placeSelectionBubble({
    ...bounds,
    selectionRect: { top: 240, bottom: 270 },
  }), { top: 192, placement: 'above' });
});

test('selection bubble flips below the selection before it can overlap the toolbar', () => {
  assert.deepEqual(placeSelectionBubble({
    ...bounds,
    selectionRect: { top: 140, bottom: 170 },
  }), { top: 178, placement: 'below' });
});

test('selection bubble is hidden once the selection leaves the editor viewport', () => {
  assert.equal(placeSelectionBubble({
    ...bounds,
    selectionRect: { top: 70, bottom: 110 },
  }), null);
  assert.equal(placeSelectionBubble({
    ...bounds,
    selectionRect: { top: 710, bottom: 740 },
  }), null);
});

test('selection bubble is hidden when neither side has enough visible room', () => {
  assert.equal(placeSelectionBubble({
    viewportTop: 120,
    viewportBottom: 210,
    bubbleHeight: 40,
    gap: 8,
    selectionRect: { top: 145, bottom: 185 },
  }), null);
});
