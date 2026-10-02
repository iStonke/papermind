export const THOUGHT_PLACEMENT_GAP = 64;

export function findFreeThoughtPosition(bounds, size, occupied, gap = THOUGHT_PLACEMENT_GAP) {
  const xs = [...new Set([bounds.x, ...occupied.map(r => r.x + r.width + gap)])].sort((a,b) => a-b);
  const ys = [...new Set([bounds.y, ...occupied.map(r => r.y + r.height + gap)])].sort((a,b) => a-b);
  for (const y of ys) for (const x of xs) {
    if (x < bounds.x || y < bounds.y || x + size.width > bounds.x + bounds.width || y + size.height > bounds.y + bounds.height) continue;
    if (occupied.every(r => x + size.width + gap <= r.x || x >= r.x + r.width + gap || y + size.height + gap <= r.y || y >= r.y + r.height + gap)) return { x, y };
  }
  return null;
}
