export function shiftedThoughtPositions(items, dx, dy) {
  if (!items.length) return [];
  const x = Math.max(-Math.min(...items.map(item => item.position.x)), Math.min(Math.round(dx), 100000-Math.max(...items.map(item => item.position.x))));
  const y = Math.max(-Math.min(...items.map(item => item.position.y)), Math.min(Math.round(dy), 100000-Math.max(...items.map(item => item.position.y))));
  return items.map(item => ({ id:item.pin.id, x:item.position.x+x, y:item.position.y+y }));
}
