export function animateInlinePlaceholderResize(element, previousBounds) {
  if (!element || !previousBounds?.width || !previousBounds.height
    || element.closest('.pm-no-animations')
    || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const frames = [previousBounds, element.getBoundingClientRect()].map(({ width, height }) => ({
    width: `${width}px`,
    height: `${height}px`,
    minWidth: '0px',
    minHeight: '0px',
    overflow: 'hidden',
  }));
  element.animate(frames, { duration: 180, easing: 'ease' });
}
