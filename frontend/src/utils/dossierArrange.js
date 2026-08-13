function visualOrder(a, b) {
  return a.y - b.y || a.x - b.x || a.sortOrder - b.sortOrder;
}

export function arrangeDossierRects(rects, options = {}) {
  if (!Array.isArray(rects) || !rects.length) return [];
  const columns = Math.max(1, Math.floor(options.columns || 1));
  const grid = Math.max(1, Number(options.grid) || 26);
  const startX = Number.isFinite(options.startX) ? options.startX : grid;
  const startY = Number.isFinite(options.startY) ? options.startY : grid;
  const gap = Number.isFinite(options.gap) ? options.gap : 20;
  const ordered = [...rects].sort(visualOrder);
  const widest = Math.max(...ordered.map((rect) => rect.w));
  const columnStep = Math.ceil((widest + gap) / grid) * grid;
  const placements = [];
  let y = startY;

  for (let index = 0; index < ordered.length; index += columns) {
    const row = ordered.slice(index, index + columns);
    const rowHeight = Math.max(...row.map((rect) => rect.h));
    row.forEach((rect, column) => {
      placements.push({ id: rect.id, x: startX + column * columnStep, y });
    });
    y = Math.ceil((y + rowHeight + gap) / grid) * grid;
  }

  return placements;
}
