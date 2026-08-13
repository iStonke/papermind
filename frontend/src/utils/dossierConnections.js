function center(rect) {
  return { x: rect.x + rect.w / 2, y: rect.y + rect.h / 2 };
}

export function resolveDossierConnectionPath(documentRect, attachedRect) {
  if (!documentRect || !attachedRect) return '';
  const documentCenter = center(documentRect);
  const attachedCenter = center(attachedRect);
  const dx = attachedCenter.x - documentCenter.x;
  const dy = attachedCenter.y - documentCenter.y;
  let from;
  let to;

  if (Math.abs(dx) >= Math.abs(dy)) {
    const direction = dx >= 0 ? 1 : -1;
    from = { x: documentCenter.x + direction * documentRect.w / 2, y: documentCenter.y };
    to = { x: attachedCenter.x - direction * attachedRect.w / 2, y: attachedCenter.y };
    const bend = Math.max(24, Math.abs(to.x - from.x) * 0.42) * direction;
    return `M ${from.x} ${from.y} C ${from.x + bend} ${from.y}, ${to.x - bend} ${to.y}, ${to.x} ${to.y}`;
  }

  const direction = dy >= 0 ? 1 : -1;
  from = { x: documentCenter.x, y: documentCenter.y + direction * documentRect.h / 2 };
  to = { x: attachedCenter.x, y: attachedCenter.y - direction * attachedRect.h / 2 };
  const bend = Math.max(24, Math.abs(to.y - from.y) * 0.42) * direction;
  return `M ${from.x} ${from.y} C ${from.x} ${from.y + bend}, ${to.x} ${to.y - bend}, ${to.x} ${to.y}`;
}
