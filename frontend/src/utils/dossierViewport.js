export function resolveDossierFit(rects, viewport, options = {}) {
  if (!Array.isArray(rects) || !rects.length || !viewport?.width || !viewport?.height) return null;

  const padding = Number.isFinite(options.padding) ? options.padding : 48;
  const minScale = Number.isFinite(options.minScale) ? options.minScale : 0.32;
  const maxScale = Number.isFinite(options.maxScale) ? options.maxScale : 1;
  const minX = Math.min(...rects.map((rect) => rect.x));
  const minY = Math.min(...rects.map((rect) => rect.y));
  const maxX = Math.max(...rects.map((rect) => rect.x + rect.w));
  const maxY = Math.max(...rects.map((rect) => rect.y + rect.h));
  const contentWidth = Math.max(1, maxX - minX);
  const contentHeight = Math.max(1, maxY - minY);
  const availableWidth = Math.max(1, viewport.width - padding * 2);
  const availableHeight = Math.max(1, viewport.height - padding * 2);
  const scale = Math.max(minScale, Math.min(maxScale, availableWidth / contentWidth, availableHeight / contentHeight));

  return {
    scale,
    x: (viewport.width - (minX + maxX) * scale) / 2,
    y: (viewport.height - (minY + maxY) * scale) / 2,
  };
}
