<template>
  <div
    ref="rootEl"
    class="preview-layout"
    :class="{
      'preview-layout--drawer-open': showDrawer && isOpen,
      'preview-layout--drawer-auto-hide': showDrawer && autoHideDrawer
    }"
  >
    <div class="preview-layout__viewer">
      <slot name="viewer" />
    </div>

    <section
      v-if="showDrawer"
      :class="[
        'preview-layout__drawer',
        'pm-drawer',
        isOpen ? 'pm-drawer--expanded' : 'pm-drawer--collapsed'
      ]"
      :style="drawerStyle"
      role="region"
      aria-label="Dokumentdetails"
    >
      <div ref="headerEl" class="preview-layout__header">
        <slot name="drawer-header" />
      </div>

      <div v-if="$slots['drawer-tabs']" v-show="isOpen" ref="tabsEl" class="preview-layout__tabs" :inert="!isOpen" :aria-hidden="!isOpen"><slot name="drawer-tabs" /></div>
      <div v-else class="pm-drawer-divider" :class="{ 'pm-drawer-divider--visible': isOpen }" aria-hidden="true" />

      <div
        :id="bodyId || fallbackBodyId"
        ref="bodyEl"
        class="preview-layout__body"
        :class="isOpen ? 'preview-layout__body--open' : 'preview-layout__body--closed'"
        :aria-hidden="String(!isOpen)"
        :inert="!isOpen"
        @scroll.passive="updateScrollCue"
      >
        <div ref="contentEl" class="preview-layout__content"><slot name="drawer-body" /></div>
      </div>
      <div class="preview-layout__scroll-cue" :class="{ 'preview-layout__scroll-cue--visible': isOpen && hasMoreBelow }" aria-hidden="true" />
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue';

const props = defineProps({
  showDrawer: { type: Boolean, default: false },
  isOpen: { type: Boolean, default: false },
  autoHideDrawer: { type: Boolean, default: false },
  contentKey: { type: [String, Number], default: '' },
  sectionKey: { type: String, default: '' },
  bodyId: { type: String, default: '' },
  collapsedHeight: { type: Number, default: 72 },
  minViewerHeight: { type: Number, default: 180 },
  expandBoundarySelector: { type: String, default: '' }
});
const fallbackBodyId = `document-details-${useId()}`;
const rootEl = ref(null);
const headerEl = ref(null);
const tabsEl = ref(null);
const tabsHeight = ref(0);
const bodyEl = ref(null);
const contentEl = ref(null);
const contentHeight = ref(0);
const openHeight = ref(0);
const containerHeight = ref(0);
const headerHeight = ref(0);
const hasMoreBelow = ref(false);
let observer;
let frame;
let swapAnimations = [];

function updateScrollCue() {
  const body = bodyEl.value;
  hasMoreBelow.value = Boolean(body && body.scrollHeight - body.clientHeight - body.scrollTop > 8);
}
function measureContent() {
  const root = rootEl.value;
  const header = headerEl.value;
  const body = bodyEl.value;
  if (!root || !header || !body) return;
  containerHeight.value = root.clientHeight;
  headerHeight.value = header.offsetHeight;
  tabsHeight.value = tabsEl.value?.offsetHeight || 0;
  const fullBody = contentEl.value?.offsetHeight || 0;
  contentHeight.value = headerHeight.value + tabsHeight.value + 1 + fullBody;
  const boundary = props.expandBoundarySelector ? body.querySelector(props.expandBoundarySelector) : null;
  const bodyCut = boundary
    ? Math.max(0, Math.round(boundary.getBoundingClientRect().top - body.getBoundingClientRect().top + body.scrollTop))
    : fullBody;
  openHeight.value = headerHeight.value + tabsHeight.value + 1 + bodyCut;
  updateScrollCue();
}
function scheduleMeasure() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(measureContent);
}
function observeLayout() {
  observer?.disconnect();
  observer = new ResizeObserver(scheduleMeasure);
  for (const el of [rootEl.value, headerEl.value, tabsEl.value, contentEl.value]) {
    if (el) observer.observe(el);
  }
  measureContent();
}
onMounted(observeLayout);
watch([headerEl, tabsEl, contentEl], () => { void nextTick(observeLayout); });
watch(() => props.isOpen, async open => {
  if (!open && (bodyEl.value?.contains(document.activeElement) || tabsEl.value?.contains(document.activeElement))) {
    headerEl.value?.querySelector('[aria-expanded]')?.focus();
  }
  await nextTick();
  measureContent();
});
function cancelSwap() {
  swapAnimations.forEach(animation => animation.cancel());
  swapAnimations = [];
}
watch(() => [props.contentKey, props.sectionKey], async ([documentKey], [previousDocumentKey]) => {
  cancelSwap();
  await nextTick();
  if (bodyEl.value) bodyEl.value.scrollTop = 0;
  measureContent();
  if (!props.isOpen || rootEl.value?.closest('.pm-no-animations')
    || window.matchMedia('(prefers-reduced-motion: reduce)').matches
    || bodyEl.value?.contains(document.activeElement)) return;
  // Animate existing nodes; field instances and keyboard focus survive.
  const elements = [contentEl.value];
  if (documentKey !== previousDocumentKey) elements.push(headerEl.value?.querySelector('.details-drawer__title-wrap'));
  for (const el of elements) {
    if (el) swapAnimations.push(el.animate([
      { opacity: 0.25, transform: 'translateY(4px)' },
      { opacity: 1, transform: 'translateY(0)' }
    ], { duration: 220, easing: 'cubic-bezier(.16, 1, .3, 1)' }));
  }
});
const drawerStyle = computed(() => {
  if (!props.isOpen) return { height: `${Math.max(props.collapsedHeight, headerHeight.value)}px` };
  const cap = Math.max(headerHeight.value + tabsHeight.value + 1, containerHeight.value - props.minViewerHeight);
  const target = openHeight.value || contentHeight.value || props.collapsedHeight;
  const height = Math.round(Math.min(target, contentHeight.value || target, cap || props.collapsedHeight));
  return { height: `${height}px` };
});
onBeforeUnmount(() => {
  observer?.disconnect();
  cancelAnimationFrame(frame);
  cancelSwap();
});
</script>

<style scoped>
.preview-layout {
  --preview-drawer-card-bg: var(--pm-app-surface-raised, rgb(var(--v-theme-surface)));
  --preview-drawer-motion-duration: 420ms;
  --preview-drawer-motion-easing: cubic-bezier(.22, 1, .36, 1);
  position: relative;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  container-type: inline-size;
  background: var(--pm-pdf-stage-bg, var(--pm-viewer-surface));
}
.preview-layout__viewer {
  flex: 1 1 0;
  min-height: 0;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--pm-pdf-stage-bg, var(--pm-viewer-surface));
}
/* The panel participates in layout: its top edge and the page above move
   together. No overlap, floating margin, backdrop or translated card. */
.preview-layout__drawer {
  flex: 0 0 auto;
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: 100%;
  border-top: 1px solid var(--pm-divider);
  background: var(--preview-drawer-card-bg);
  box-shadow: 0 -6px 24px rgb(0 0 0 / .045);
  transition: height var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing), opacity 180ms ease;
}
.preview-layout__drawer::before {
  content: ''; position: absolute; inset: 0 auto auto 0; height: 2px; width: 100%;
  z-index: 4; pointer-events: none; transform: scaleX(0); transform-origin: left;
  background: color-mix(in srgb, var(--pm-accent) 65%, transparent);
  transition: transform 540ms var(--preview-drawer-motion-easing);
}
.preview-layout--drawer-open .preview-layout__drawer::before { transform: scaleX(1); }
.preview-layout__header {
  position: relative;
  z-index: 2;
  flex: 0 0 auto;
  min-height: 56px;
  background: var(--preview-drawer-card-bg);
}
.pm-drawer-divider { width: 100%; height: 1px; flex: 0 0 1px; opacity: 0; background: var(--pm-divider-soft, var(--pm-divider)); transition: opacity 160ms ease; }
.pm-drawer-divider--visible { opacity: 1; }
.preview-layout__tabs { flex: 0 0 auto; min-width: 0; }
.preview-layout__body { flex: 1 1 auto; min-height: 0; overflow: hidden; opacity: 0; transition: opacity 80ms ease; }
.preview-layout__body--open { opacity: 1; overflow-y: auto; transition: opacity 200ms ease 90ms; scrollbar-gutter: stable; }
.preview-layout__body--closed { pointer-events: none; }
.preview-layout__content { display: flow-root; min-width: 0; }
.preview-layout__body :deep(.pm-metadata-row) { opacity: 0; transform: translateY(5px); transition: opacity 70ms ease, transform 70ms ease; }
.preview-layout__body--open :deep(.pm-metadata-row) { opacity: 1; transform: none; transition: opacity 200ms ease var(--field-enter-delay, 100ms), transform 260ms var(--preview-drawer-motion-easing) var(--field-enter-delay, 100ms); }
.preview-layout__body :deep(.pm-metadata-row:nth-child(2)) { --field-enter-delay: 120ms; }
.preview-layout__body :deep(.pm-metadata-row:nth-child(3)) { --field-enter-delay: 140ms; }
.preview-layout__body :deep(.pm-metadata-row:nth-child(4)) { --field-enter-delay: 160ms; }
.preview-layout__body :deep(.pm-metadata-row:nth-child(5)) { --field-enter-delay: 180ms; }
.preview-layout__scroll-cue { position: absolute; bottom: 0; inset-inline: 0; height: 20px; z-index: 3; pointer-events: none; opacity: 0; background: linear-gradient(transparent, var(--preview-drawer-card-bg)); transition: opacity 180ms ease; }
.preview-layout__scroll-cue--visible { opacity: 1; }
.preview-layout--drawer-auto-hide:not(:hover):not(:focus-within) .preview-layout__drawer { opacity: .45; }
.pm-drawer :deep(:focus-visible) { outline: 2px solid color-mix(in srgb, var(--pm-accent) 55%, transparent); outline-offset: 2px; border-radius: 6px; }
:global(.pm-no-animations .preview-layout__drawer),
:global(.pm-no-animations .preview-layout__drawer::before),
:global(.pm-no-animations .preview-layout__body),
:global(.pm-no-animations .preview-layout__scroll-cue),
:global(.pm-no-animations .preview-layout__body .pm-metadata-row) { transition: none; }
:global(.pm-no-animations .preview-layout__body .pm-metadata-row) { transform: none; }
@media (prefers-reduced-motion: reduce) {
  .preview-layout__drawer, .preview-layout__drawer::before, .preview-layout__body,
  .preview-layout__scroll-cue,
  .preview-layout__body :deep(.pm-metadata-row) { transition: none; }
  .preview-layout__body :deep(.pm-metadata-row) { transform: none; }
}
</style>
