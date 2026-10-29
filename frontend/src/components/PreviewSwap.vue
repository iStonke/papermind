<template>
  <div ref="root" class="preview-swap" :aria-busy="pending"
    @pointerdown.capture="settleEntrance" @wheel.capture.passive="settleEntrance" @keydown.capture="settleEntrance">
    <div class="preview-swap__live" :class="{ 'preview-swap__live--pending': pending }" :inert="pending">
      <slot />
    </div>
    <div ref="snapshotHost" class="preview-swap__snapshot" :class="{ 'preview-swap__snapshot--leaving': !pending }" aria-hidden="true" inert />
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
const props = defineProps({ transitionKey: [String, Number] });
const root = ref(null);
const snapshotHost = ref(null);
const pending = ref(false);
let cleanupTimer;
let fallbackTimer;
let generation = 0;
let revealedKey = Symbol();
let entranceAnimations = [];

function motionEnabled() {
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    && !root.value?.closest('.pm-no-animations');
}
function clearSnapshot() {
  window.clearTimeout(cleanupTimer);
  window.clearTimeout(fallbackTimer);
  snapshotHost.value?.replaceChildren();
  pending.value = false;
}
function cancelEntrance() {
  entranceAnimations.forEach(animation => animation.cancel());
  entranceAnimations = [];
}
function settleEntrance() {
  if (pending.value || !entranceAnimations.length) return;
  cancelEntrance();
  clearSnapshot();
}

// Copy only the visible, rendered PDF pixels. No second PDF instance, text
// layer, focusable controls or duplicate IDs survive the document change.
function capture() {
  if (!motionEnabled()) { clearSnapshot(); return; }
  // A rapid second selection keeps the last complete image, never a loader.
  if (pending.value) return;
  const host = snapshotHost.value;
  const live = root.value?.querySelector('.preview-swap__live');
  if (!host || !live?.querySelector('.pdf-preview--document-ready')) { clearSnapshot(); return; }
  const bounds = root.value.getBoundingClientRect();
  const image = document.createElement('div');
  image.style.cssText = 'position:absolute;inset:0;background:var(--pm-pdf-stage-bg, var(--pm-viewer-surface, #e9e9e9))';
  let count = 0;
  for (const canvas of live.querySelectorAll('canvas')) {
    const rect = canvas.getBoundingClientRect();
    if (!canvas.width || !canvas.height || rect.bottom <= bounds.top || rect.top >= bounds.bottom || rect.right <= bounds.left || rect.left >= bounds.right) continue;
    const copy = document.createElement('canvas');
    copy.width = canvas.width;
    copy.height = canvas.height;
    copy.getContext('2d').drawImage(canvas, 0, 0);
    copy.style.cssText = `position:absolute;left:${rect.left - bounds.left}px;top:${rect.top - bounds.top}px;width:${rect.width}px;height:${rect.height}px;`;
    image.append(copy);
    count++;
  }
  if (!count) { clearSnapshot(); return; }
  window.clearTimeout(cleanupTimer);
  host.replaceChildren(image);
  pending.value = true;
}
function reveal(key) {
  if (key !== props.transitionKey || key === revealedKey) return;
  revealedKey = key;
  const token = generation;
  window.clearTimeout(fallbackTimer);
  // The first-page event fires just before Vue applies the ready class.
  void nextTick(async () => {
    if (key !== props.transitionKey || token !== generation) return;
    pending.value = false;
    await nextTick();
    if (key !== props.transitionKey || token !== generation) return;
    cancelEntrance();
    if (!motionEnabled()) { clearSnapshot(); return; }
    const live = root.value?.querySelector('.preview-swap__live');
    const paper = live?.querySelector('.pdf-preview__pages');
    if (live) entranceAnimations.push(live.animate([
      { opacity: 0 }, { opacity: 1 }
    ], { duration: 460, easing: 'cubic-bezier(.4, 0, .2, 1)', fill: 'backwards' }));
    if (paper) entranceAnimations.push(paper.animate([
      { transform: 'perspective(1200px) translateY(12px) scale(.985) rotateX(1.2deg)' },
      { transform: 'none' }
    ], { duration: 640, easing: 'cubic-bezier(.16, 1, .3, 1)', fill: 'backwards' }));
    cleanupTimer = window.setTimeout(() => {
      if (token !== generation) return;
      cancelEntrance();
      clearSnapshot();
    }, 700);
  });
}
watch(() => props.transitionKey, () => {
  generation++;
  revealedKey = Symbol();
  window.clearTimeout(cleanupTimer);
  cancelEntrance();
  capture();
  window.clearTimeout(fallbackTimer);
  // Rendering failures must never leave a stale document covering an error.
  fallbackTimer = window.setTimeout(() => reveal(props.transitionKey), 12000);
}, { flush: 'pre' });
onBeforeUnmount(() => { generation++; cancelEntrance(); clearSnapshot(); });
defineExpose({ reveal, settleEntrance });
</script>

<style scoped>
.preview-swap { position: relative; display: flex; flex: 1; min-width: 0; min-height: 0; overflow: hidden; }
.preview-swap__live { display: flex; flex: 1; min-width: 0; min-height: 0; opacity: 1; }
.preview-swap__live--pending { opacity: 0; pointer-events: none; }
/* One owner for the fade; PDF controls stay still while only the paper settles. */
.preview-swap__live :deep(.pdf-preview__viewer) { transition: none; }
.preview-swap__snapshot { position: absolute; inset: 0; overflow: hidden; pointer-events: none; opacity: 1; transform: none; transition: opacity 460ms cubic-bezier(.4, 0, .2, 1), transform 640ms cubic-bezier(.16, 1, .3, 1); }
.preview-swap__snapshot:not(.preview-swap__snapshot--leaving) { transition: none; }
.preview-swap__snapshot--leaving { opacity: 0; transform: translateY(-3px) scale(.992); }
:global(.pm-no-animations .preview-swap__live),
:global(.pm-no-animations .preview-swap__snapshot) { transition: none; transform: none; }
@media (prefers-reduced-motion: reduce) {
  .preview-swap__live, .preview-swap__snapshot { transition: none; transform: none; }
}
</style>
