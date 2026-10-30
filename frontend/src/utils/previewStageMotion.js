// Shared between DocumentPreviewLayout (drawer motion) and PdfPreview (page
// scale). The layout provides `{ motion, bottomInset }`: each drawer move is
// announced so the fitted page can follow it with a compositor-only transform
// instead of re-laying out every frame, and the bottom inset arrives as a
// number so no inherited custom property restyles the whole text layer.
export const PREVIEW_STAGE = Symbol('pm-preview-stage');

const FALLBACK_EASING = 'cubic-bezier(.22, 1, .36, 1)';

// Evenly spaced stops of a CSS linear() easing, or null for anything else.
function linearEasingStops(easing) {
  const match = /^linear\((.*)\)$/.exec(easing.trim());
  if (!match) return null;
  const stops = match[1].split(',').map(stop => Number(stop.trim()));
  return stops.length > 1 && stops.every(Number.isFinite) ? stops : null;
}

// Animates `frameAt(progress)` from 0 to 1. A linear() spring is expanded into
// keyframes with linear segments (the same curve): Core Animation cannot run
// linear() easings itself, so Safari would otherwise tick it on the main thread.
export function animateTravel(el, frameAt, { duration, easing, delay = 0, fill = 'none' }) {
  const stops = linearEasingStops(easing);
  if (stops) {
    const keyframes = stops.map((progress, index) => ({ offset: index / (stops.length - 1), ...frameAt(progress) }));
    return el.animate(keyframes, { duration, delay, fill, easing: 'linear' });
  }
  const options = { duration, delay, fill, easing };
  try {
    return el.animate([frameAt(0), frameAt(1)], options);
  } catch {
    // Unsupported easing syntax in older engines.
    return el.animate([frameAt(0), frameAt(1)], { ...options, easing: FALLBACK_EASING });
  }
}

export function activeStageMotion(motion, now = performance.now()) {
  return motion && now - motion.start < motion.duration ? motion : null;
}

export function currentTranslateY(el) {
  const transform = getComputedStyle(el).transform;
  return transform && transform !== 'none' ? new DOMMatrixReadOnly(transform).m42 : 0;
}

export function currentScale(el) {
  const transform = getComputedStyle(el).transform;
  return transform && transform !== 'none' ? new DOMMatrixReadOnly(transform).a : 1;
}
