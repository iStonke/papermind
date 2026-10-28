<template>
  <div ref="root" class="preview-swap" :aria-busy="pending">
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

// Copy only the visible, rendered PDF pixels. No second PDF instance, text
// layer, focusable controls or duplicate IDs survive the document change.
function capture() {
  if (!motionEnabled()) { clearSnapshot(); return; }
  // A rapid second selection keeps the last complete image, never a loader.
  if (pending.value) return;
  const host = snapshotHost.value;
  const live = root.value?.querySelector('.preview-swap__live');
  if (!host || !live?.querySelector('.pdf-preview--document-ready')) return;
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
  if (!count) return;
  window.clearTimeout(cleanupTimer);
  host.replaceChildren(image);
  pending.value = true;
}
function reveal(key) {
  if (key !== props.transitionKey) return;
  window.clearTimeout(fallbackTimer);
  // The first-page event fires just before Vue applies the ready class.
  void nextTick(() => {
    if (key !== props.transitionKey) return;
    pending.value = false;
    cleanupTimer = window.setTimeout(clearSnapshot, 280);
  });
}
watch(() => props.transitionKey, () => {
  capture();
  window.clearTimeout(fallbackTimer);
  // Rendering failures must never leave a stale document covering an error.
  fallbackTimer = window.setTimeout(() => reveal(props.transitionKey), 12000);
}, { flush: 'pre' });
onBeforeUnmount(clearSnapshot);
defineExpose({ reveal });
</script>

<style scoped>
.preview-swap { position: relative; display: flex; flex: 1; min-width: 0; min-height: 0; overflow: hidden; }
.preview-swap__live { display: flex; flex: 1; min-width: 0; min-height: 0; opacity: 1; transform: translateY(0); transition: opacity 240ms ease, transform 280ms cubic-bezier(.16, 1, .3, 1); }
.preview-swap__live--pending { opacity: 0; transform: translateY(8px); pointer-events: none; transition: none; }
.preview-swap__snapshot { position: absolute; inset: 0; overflow: hidden; pointer-events: none; opacity: 1; transition: opacity 240ms ease; }
.preview-swap__snapshot--leaving { opacity: 0; }
:global(.pm-no-animations .preview-swap__live),
:global(.pm-no-animations .preview-swap__snapshot) { transition: none; transform: none; }
@media (prefers-reduced-motion: reduce) {
  .preview-swap__live, .preview-swap__snapshot { transition: none; transform: none; }
}
</style>
