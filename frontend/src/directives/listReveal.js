/** One entrance per list/context; no replay on typing, appending or scrolling. */
const states = new WeakMap();
const EXCLUDED = '.is-new, .is-removing, .is-editing, .is-dragging, .pm-import-arrival, .document-row--just-arrived, .document-row--arrival-marker-pending, .document-row--removing';
export const LIST_REVEAL_STEP = 55;
export const LIST_REVEAL_DURATION = 500;

function disabled(el) {
  return Boolean(el.closest('.pm-no-animations')) || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
function releasePending(state) {
  state.pending.forEach(animation => animation.cancel());
  state.pending.clear();
}
function stop(state) {
  state.armed = false;
  cancelAnimationFrame(state.frame);
  state.frame = 0;
  state.mutations.disconnect();
  state.resize.disconnect();
  state.intersection.disconnect();
  releasePending(state);
  state.animations.forEach(animation => animation.cancel());
  state.animations = [];
}
function stage(el, state) {
  if (!state.armed) return;
  if (disabled(el)) { stop(state); return; }
  const items = new Set([...el.querySelectorAll(state.options.selector || ':scope > li')]
    .filter(item => !item.matches(EXCLUDED) && !item.closest('[contenteditable="true"]')));
  for (const [item, animation] of state.pending) {
    if (!items.has(item)) { animation.cancel(); state.pending.delete(item); }
  }
  for (const item of items) {
    if (state.pending.has(item)) continue;
    // Hold the first frame before layout/readiness callbacks can paint the rows.
    // A paused effect avoids changing inline styles or triggering CSS transitions.
    const mask = item.animate([{ opacity: 0 }, { opacity: 0 }], { duration: 1, fill: 'both' });
    mask.pause();
    mask.currentTime = 0;
    state.pending.set(item, mask);
  }
}
function visibleBounds(el) {
  const rect = el.getBoundingClientRect();
  const bounds = { top: Math.max(0, rect.top), bottom: Math.min(innerHeight, rect.bottom), left: Math.max(0, rect.left), right: Math.min(innerWidth, rect.right) };
  for (let parent = el.parentElement; parent; parent = parent.parentElement) {
    const style = getComputedStyle(parent), clip = parent.getBoundingClientRect();
    if (/(auto|scroll|hidden|clip)/.test(style.overflowY)) { bounds.top = Math.max(bounds.top, clip.top); bounds.bottom = Math.min(bounds.bottom, clip.bottom); }
    if (/(auto|scroll|hidden|clip)/.test(style.overflowX)) { bounds.left = Math.max(bounds.left, clip.left); bounds.right = Math.min(bounds.right, clip.right); }
  }
  return bounds;
}
function reveal(el, state) {
  state.frame = 0;
  if (!state.armed || state.options.ready === false) return;
  if (disabled(el)) { stop(state); return; }
  if (getComputedStyle(el).visibility === 'hidden') return;
  const bounds = visibleBounds(el);
  if (bounds.bottom <= bounds.top || bounds.right <= bounds.left) return;
  const visible = [];
  for (const item of el.querySelectorAll(state.options.selector || ':scope > li')) {
    if (item.matches(EXCLUDED) || item.closest('[contenteditable="true"]')) continue;
    const rect = item.getBoundingClientRect();
    if (rect.width && rect.height && rect.bottom > bounds.top && rect.top < bounds.bottom && rect.right > bounds.left && rect.left < bounds.right) visible.push(item);
    if (visible.length === 10) break;
  }
  if (!visible.length) return;
  state.armed = false;
  state.resize.disconnect();
  state.intersection.disconnect();
  visible.forEach((item, index) => {
    const delay = index * LIST_REVEAL_STEP;
    const fade = item.animate([{ opacity: 0 }, { opacity: 1 }], { duration: LIST_REVEAL_DURATION, delay, easing: 'ease-in-out', fill: 'backwards' });
    const move = item.animate([{ transform: 'translateY(7px)' }, { transform: 'translateY(0)' }], { duration: 360, delay, easing: 'cubic-bezier(.16, 1, .3, 1)', fill: 'backwards' });
    state.animations.push(fade, move);
  });
  // Install the fades before releasing their initial-frame masks, in one task.
  releasePending(state);
  const current = state.animations;
  void Promise.allSettled(current.map(animation => animation.finished)).then(() => {
    if (state.animations === current) {
      state.animations = [];
      state.mutations.disconnect();
    }
  });
}
function queue(el, state) {
  if (!state.armed || state.frame) return;
  state.frame = requestAnimationFrame(() => reveal(el, state));
}
function arm(el, state) {
  stop(state);
  state.armed = true;
  state.mutations.observe(el, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  state.resize.observe(el);
  state.intersection.observe(el);
  stage(el, state);
  queue(el, state);
}
export const vListReveal = {
  mounted(el, binding) {
    const state = { options: binding.value || {}, armed: true, frame: 0, animations: [], pending: new Map() };
    state.mutations = new MutationObserver(() => {
      if (state.armed) { stage(el, state); queue(el, state); }
      else {
        // Deleting, dragging or an import landing takes over this row's motion.
        state.animations.forEach(animation => {
          const item = animation.effect?.target;
          if (!item?.isConnected || item.matches(EXCLUDED)) animation.cancel();
        });
      }
    });
    state.resize = new ResizeObserver(() => queue(el, state));
    state.intersection = new IntersectionObserver(() => queue(el, state));
    state.scroll = () => stop(state);
    state.media = window.matchMedia('(prefers-reduced-motion: reduce)');
    state.motionChange = () => { if (state.media.matches) stop(state); };
    state.media.addEventListener('change', state.motionChange);
    el.addEventListener('scroll', state.scroll, { capture: true, passive: true });
    states.set(el, state);
    arm(el, state);
  },
  updated(el, binding) {
    const state = states.get(el);
    if (!state) return;
    const previousKey = state.options.key;
    state.options = binding.value || {};
    if (!Object.is(previousKey, state.options.key)) arm(el, state);
    else if (disabled(el)) stop(state);
    else { stage(el, state); queue(el, state); }
  },
  unmounted(el) {
    const state = states.get(el);
    if (!state) return;
    stop(state);
    state.media.removeEventListener('change', state.motionChange);
    el.removeEventListener('scroll', state.scroll, true);
    states.delete(el);
  }
};
