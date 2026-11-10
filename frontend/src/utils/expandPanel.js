/**
 * Aufklapp-Panels in Kachelrastern (Muster „Bildergalerie“): Die Kacheln
 * bleiben stehen, ein Panel wird hinter dem letzten Element der Zeile der
 * angeklickten Kachel eingefügt und wächst in der Höhe auf.
 *
 * Genutzt von CollectionMemberTiles (Mitglieder) und
 * CorrespondentDocumentGrid (Dokumente).
 */
import { nextTick } from 'vue';

export const PANEL_EASE = 'cubic-bezier(0.2, 0.8, 0.2, 1)';
export const PANEL_OPEN_MS = 320;
export const PANEL_CLOSE_MS = 240;

export function motionOff() {
  if (typeof window === 'undefined') return true;
  return Boolean(document.querySelector('.papermind-app.pm-no-animations'))
    || Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
}

/** Anzahl der aufgelösten Spalten eines CSS-Grids (auch bei auto-fill). */
export function countColumns(el) {
  const tracks = el ? getComputedStyle(el).gridTemplateColumns : '';
  return tracks && tracks !== 'none' ? Math.max(1, tracks.trim().split(/\s+/).length) : 1;
}

/** Index des letzten Elements in der Zeile von `index` (−1 ohne Auswahl). */
export function rowEnd(index, cols, length) {
  if (index < 0 || length <= 0) return -1;
  const perRow = Math.max(1, cols);
  return Math.min(Math.floor(index / perRow) * perRow + perRow - 1, length - 1);
}

/**
 * Transition-Hook @enter: Höhe (und Abstand nach unten) von 0 auf den
 * Endwert. Der Abstand muss als margin-bottom anliegen, nicht als row-gap.
 */
export function animatePanelEnter(el, done, after) {
  const finish = () => {
    el.style.overflow = '';
    done();
    after?.();
  };
  if (motionOff()) { finish(); return; }
  const height = el.getBoundingClientRect().height;
  const gap = getComputedStyle(el).marginBottom;
  el.style.overflow = 'hidden';
  const anim = el.animate(
    [
      { height: '0px', marginBottom: '0px', opacity: 0 },
      { height: `${height}px`, marginBottom: gap, opacity: 1 },
    ],
    { duration: PANEL_OPEN_MS, easing: PANEL_EASE },
  );
  anim.onfinish = finish;
  anim.oncancel = finish;
}

/** Transition-Hook @leave: Gegenstück zu animatePanelEnter. */
export function animatePanelLeave(el, done) {
  el.classList.add('is-leaving');
  el.removeAttribute('id');
  if (motionOff()) { done(); return; }
  const height = el.getBoundingClientRect().height;
  const gap = getComputedStyle(el).marginBottom;
  el.style.overflow = 'hidden';
  el.style.pointerEvents = 'none';
  const anim = el.animate(
    [
      { height: `${height}px`, marginBottom: gap, opacity: 1 },
      { height: '0px', marginBottom: '0px', opacity: 0 },
    ],
    { duration: PANEL_CLOSE_MS, easing: PANEL_EASE, fill: 'forwards' },
  );
  anim.onfinish = done;
  anim.oncancel = done;
}

/** Höhenwechsel eines offenen Panels (Inhaltswechsel) weich überblenden. */
export async function tweenHeight(el, mutate) {
  if (!el || motionOff() || el.getAnimations().some((a) => a.playState === 'running')) {
    await mutate();
    return;
  }
  const from = el.getBoundingClientRect().height;
  await mutate();
  await nextTick();
  if (!el.isConnected) return;
  const to = el.getBoundingClientRect().height;
  if (Math.abs(from - to) < 1) return;
  el.style.overflow = 'hidden';
  const anim = el.animate([{ height: `${from}px` }, { height: `${to}px` }], { duration: PANEL_OPEN_MS, easing: PANEL_EASE });
  const reset = () => { el.style.overflow = ''; };
  anim.onfinish = reset;
  anim.oncancel = reset;
}

function scrollParent(el) {
  for (let node = el?.parentElement; node && node !== document.body; node = node.parentElement) {
    const { overflowY } = getComputedStyle(node);
    if (/(auto|scroll)/.test(overflowY) && node.scrollHeight > node.clientHeight) return node;
  }
  return document.scrollingElement || document.documentElement;
}

/** Kachel + Panel sichtbar machen, ohne die Kachel aus dem Blick zu schieben. */
export function revealPanel(anchor, target) {
  if (!anchor || !target) return;
  const scroller = scrollParent(target);
  const isRoot = scroller === document.scrollingElement || scroller === document.documentElement;
  const view = isRoot ? { top: 0, bottom: window.innerHeight } : scroller.getBoundingClientRect();
  const a = anchor.getBoundingClientRect();
  const t = target.getBoundingClientRect();
  const pad = 12;
  let delta = 0;
  if (a.top < view.top + pad) delta = a.top - view.top - pad;
  else if (t.bottom > view.bottom - pad) delta = Math.min(t.bottom - view.bottom + pad, a.top - view.top - pad);
  if (Math.abs(delta) > 1) scroller.scrollBy({ top: delta, behavior: motionOff() ? 'auto' : 'smooth' });
}

/** Spaltenzahl eines Rasters reaktiv halten (ResizeObserver). */
export function observeColumns(el, onChange) {
  if (!el) return () => {};
  onChange(countColumns(el));
  if (typeof ResizeObserver === 'undefined') return () => {};
  const observer = new ResizeObserver(() => onChange(countColumns(el)));
  observer.observe(el);
  return () => observer.disconnect();
}
