/**
 * Ablage-Flug beim Zuordnen: das Vorschaubild einer Karte fliegt im Bogen auf
 * die Zeile des Korrespondenten in der linken Liste, die dort kurz aufleuchtet
 * (wie der Import-Flug in die Dokumentenliste).
 *
 * Reine DOM-/Web-Animations-Hilfen ohne Vue; Aufrufer prüfen vorher motionOff().
 */

const FLIGHT_MS = 680;
const ARC_SAMPLES = 10;

/** Ist das Element tatsächlich zu sehen (Größe > 0, nicht aus einem Scrollbereich gescrollt)? */
export function isVisibleInScroller(el) {
  if (!el?.isConnected) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return false;
  const centerY = rect.top + rect.height / 2;
  if (centerY < 0 || centerY > window.innerHeight) return false;
  for (let parent = el.parentElement; parent; parent = parent.parentElement) {
    const { overflowY } = getComputedStyle(parent);
    if (overflowY === 'visible') continue;
    const box = parent.getBoundingClientRect();
    if (centerY < box.top || centerY > box.bottom) return false;
  }
  return true;
}

/**
 * Sichtbare Zielzeile: der Korrespondent selbst, sonst die nächste sichtbare
 * übergeordnete Zeile (zugeklappte Sammlung). `null`, wenn nichts zu sehen ist.
 */
export function findFlightTarget(root, correspondentId, findById) {
  const seen = new Set();
  for (let id = correspondentId; id && !seen.has(id); id = findById?.(id)?.parent_id) {
    seen.add(id);
    const row = root?.querySelector(`[data-correspondent-id="${CSS.escape(String(id))}"]`);
    if (isVisibleInScroller(row)) return row;
  }
  return null;
}

function arcFrames(dx, dy) {
  // Quadratische Bézierkurve mit Scheitel über der Strecke: wirkt wie ein Wurf.
  const cx = dx * 0.45;
  const cy = Math.min(0, dy) - Math.max(60, Math.abs(dx) * 0.18);
  return Array.from({ length: ARC_SAMPLES + 1 }, (_, index) => {
    const t = index / ARC_SAMPLES;
    const x = 2 * (1 - t) * t * cx + t * t * dx;
    const y = 2 * (1 - t) * t * cy + t * t * dy;
    const rotate = -12 * Math.sin(Math.PI * t) + (t > 0.8 ? -4 * t : 0);
    const scale = 1 - 0.78 * t * t;
    return {
      offset: t,
      transform: `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) rotate(${rotate.toFixed(2)}deg) scale(${scale.toFixed(3)})`,
      opacity: t < 0.85 ? 1 : 1 - (t - 0.85) * 3,
    };
  });
}

/** Zielzeile leuchtet auf, die Zahl hüpft kurz (Web Animations – Vue setzt Klassen ggf. neu). */
export function pulseTarget(row) {
  if (!row?.isConnected || typeof row.animate !== 'function') return;
  const accent = getComputedStyle(row).getPropertyValue('--pm-accent').trim() || '#14b8a6';
  const glow = `color-mix(in srgb, ${accent} 22%, transparent)`;
  const ring = `color-mix(in srgb, ${accent} 55%, transparent)`;
  row.animate([
    { backgroundColor: glow, borderColor: ring, offset: 0.12 },
    { backgroundColor: glow, borderColor: ring, offset: 0.45 },
    { backgroundColor: 'transparent', borderColor: 'transparent' },
  ], { duration: 1100, easing: 'ease-out' });
  const count = row.querySelector('.corr-row__count');
  count?.animate([
    { transform: 'scale(1)' },
    { transform: 'scale(1.45)', color: accent, offset: 0.4 },
    { transform: 'scale(1)' },
  ], { duration: 560, easing: 'cubic-bezier(.34, 1.56, .64, 1)' });
}

/**
 * Lässt eine Kopie von `sourceEl` auf `targetEl` fliegen. Liefert ein Promise,
 * das nach der Landung (inkl. Aufleuchten) erfüllt ist.
 */
export function flyDocumentTo(sourceEl, targetEl, { duration = FLIGHT_MS } = {}) {
  if (!sourceEl || !targetEl || typeof sourceEl.animate !== 'function') return Promise.resolve();
  const from = sourceEl.getBoundingClientRect();
  const to = targetEl.getBoundingClientRect();
  const host = sourceEl.closest('.papermind-app') || document.body;

  const ghost = sourceEl.cloneNode(true);
  ghost.removeAttribute('id');
  ghost.setAttribute('aria-hidden', 'true');
  ghost.tabIndex = -1;
  ghost.classList.add('pm-assign-flight');
  Object.assign(ghost.style, {
    position: 'fixed',
    left: `${from.left}px`,
    top: `${from.top}px`,
    width: `${from.width}px`,
    height: `${from.height}px`,
    margin: '0',
    zIndex: '2400',
    pointerEvents: 'none',
    transformOrigin: 'center center',
    willChange: 'transform, opacity',
  });
  host.appendChild(ghost);

  // Landepunkt: rechts in der Zeile, bei der Dokumentzahl.
  const landX = to.right - 26 - (from.left + from.width / 2);
  const landY = to.top + to.height / 2 - (from.top + from.height / 2);
  const original = sourceEl.style.visibility;
  sourceEl.style.visibility = 'hidden';

  const flight = ghost.animate(arcFrames(landX, landY), {
    duration,
    easing: 'cubic-bezier(.45, 0, .2, 1)',
    fill: 'forwards',
  });
  return flight.finished
    .catch(() => {})
    .then(() => {
      ghost.remove();
      if (sourceEl.isConnected) sourceEl.style.visibility = original;
      pulseTarget(targetEl);
    });
}
