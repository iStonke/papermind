const AXIS_ANCHORS = Object.freeze({
  x: [
    ['start', (rect) => rect.x],
    ['center', (rect) => rect.x + rect.w / 2],
    ['end', (rect) => rect.x + rect.w],
  ],
  y: [
    ['start', (rect) => rect.y],
    ['center', (rect) => rect.y + rect.h / 2],
    ['end', (rect) => rect.y + rect.h],
  ],
});

function nearestAxisMatch(moving, others, axis, threshold) {
  let best = null;
  for (const [movingKind, movingValueOf] of AXIS_ANCHORS[axis]) {
    const movingValue = movingValueOf(moving);
    for (const other of others) {
      for (const [targetKind, targetValueOf] of AXIS_ANCHORS[axis]) {
        // Centers align with centers; either outer edge may align with another
        // edge, which also permits clean adjacent placement.
        if ((movingKind === 'center') !== (targetKind === 'center')) continue;
        const targetValue = targetValueOf(other);
        const delta = targetValue - movingValue;
        const distance = Math.abs(delta);
        if (distance > threshold || (best && distance >= best.distance)) continue;
        best = {
          kind: movingKind === targetKind ? movingKind : `${movingKind}-${targetKind}`,
          coordinate: targetValue,
          delta,
          distance,
          other,
        };
      }
    }
  }
  return best;
}

/**
 * Finds the nearest matching edge or center line on each axis.
 * Coordinates are logical board pixels, independent of the current zoom.
 */
export function resolveDossierSmartGuides(moving, others, threshold = 7) {
  if (!moving || !Array.isArray(others) || !others.length) return { x: null, y: null };

  const xMatch = nearestAxisMatch(moving, others, 'x', threshold);
  const yMatch = nearestAxisMatch(moving, others, 'y', threshold);
  const snapped = {
    ...moving,
    x: moving.x + (xMatch?.delta || 0),
    y: moving.y + (yMatch?.delta || 0),
  };

  return {
    x: xMatch ? {
      kind: xMatch.kind,
      coordinate: xMatch.coordinate,
      delta: xMatch.delta,
      from: Math.max(0, Math.min(snapped.y, xMatch.other.y) - 12),
      to: Math.max(snapped.y + snapped.h, xMatch.other.y + xMatch.other.h) + 12,
    } : null,
    y: yMatch ? {
      kind: yMatch.kind,
      coordinate: yMatch.coordinate,
      delta: yMatch.delta,
      from: Math.max(0, Math.min(snapped.x, yMatch.other.x) - 12),
      to: Math.max(snapped.x + snapped.w, yMatch.other.x + yMatch.other.w) + 12,
    } : null,
  };
}
