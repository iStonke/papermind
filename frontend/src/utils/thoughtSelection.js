export function selectionRect(start, end) {
  return { x:Math.min(start.x,end.x), y:Math.min(start.y,end.y), width:Math.abs(end.x-start.x), height:Math.abs(end.y-start.y) };
}
export function intersectingThoughtIds(rect, cards) {
  return cards.filter(card => rect.x < card.x+card.width && rect.x+rect.width > card.x && rect.y < card.y+card.height && rect.y+rect.height > card.y).map(card => card.id);
}
