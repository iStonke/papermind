export function placeSelectionBubble({
  selectionRect,
  viewportTop,
  viewportBottom,
  bubbleHeight,
  gap = 8,
}) {
  const topBoundary = Number(viewportTop);
  const bottomBoundary = Number(viewportBottom);
  const height = Math.max(0, Number(bubbleHeight) || 0);
  const spacing = Math.max(0, Number(gap) || 0);

  if (
    !selectionRect
    || !Number.isFinite(topBoundary)
    || !Number.isFinite(bottomBoundary)
    || bottomBoundary <= topBoundary
    || selectionRect.bottom <= topBoundary
    || selectionRect.top >= bottomBoundary
  ) {
    return null;
  }

  const above = selectionRect.top - spacing - height;
  if (above >= topBoundary) return { top: above, placement: 'above' };

  const below = selectionRect.bottom + spacing;
  if (below + height <= bottomBoundary) return { top: below, placement: 'below' };

  return null;
}
