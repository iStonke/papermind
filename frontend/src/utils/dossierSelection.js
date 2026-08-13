function normalizedRect(rect) {
  const x1 = Math.min(rect.x1, rect.x2);
  const x2 = Math.max(rect.x1, rect.x2);
  const y1 = Math.min(rect.y1, rect.y2);
  const y2 = Math.max(rect.y1, rect.y2);
  return { x1, x2, y1, y2 };
}

export function dossierRectIntersects(selection, card) {
  const rect = normalizedRect(selection);
  return (
    card.x < rect.x2
    && card.x + card.w > rect.x1
    && card.y < rect.y2
    && card.y + card.h > rect.y1
  );
}

export function dossierSelectionIds(selection, cards) {
  return cards.filter((card) => dossierRectIntersects(selection, card)).map((card) => card.id);
}

export function alignDossierRects(cards, mode) {
  if (!Array.isArray(cards) || cards.length < 2) return [];
  const left = Math.min(...cards.map((card) => card.x));
  const top = Math.min(...cards.map((card) => card.y));
  const right = Math.max(...cards.map((card) => card.x + card.w));
  const bottom = Math.max(...cards.map((card) => card.y + card.h));
  const centerX = (left + right) / 2;
  const centerY = (top + bottom) / 2;

  return cards.map((card) => {
    let x = card.x;
    let y = card.y;
    if (mode === 'left') x = left;
    else if (mode === 'center-x') x = centerX - card.w / 2;
    else if (mode === 'right') x = right - card.w;
    else if (mode === 'top') y = top;
    else if (mode === 'center-y') y = centerY - card.h / 2;
    else if (mode === 'bottom') y = bottom - card.h;
    return { id: card.id, x: Math.round(x), y: Math.round(y) };
  });
}
