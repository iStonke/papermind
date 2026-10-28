<template>
  <div
    ref="rootEl"
    class="preview-layout"
    :class="{
      'preview-layout--floating-card': floatingCard,
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
      <div class="preview-layout__handle" aria-hidden="true"><span /></div>
      <div ref="headerEl" class="preview-layout__header">
        <slot name="drawer-header" />
      </div>

      <div class="pm-drawer-divider" :class="{ 'pm-drawer-divider--visible': isOpen }" aria-hidden="true" />

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
  floatingCard: { type: Boolean, default: false },
  contentKey: { type: [String, Number], default: '' },
  bodyId: { type: String, default: '' },
  collapsedHeight: { type: Number, default: 72 },
  minViewerHeight: { type: Number, default: 140 },
  expandBoundarySelector: { type: String, default: '[data-drawer-expand-boundary]' }
});
const fallbackBodyId = `document-details-${useId()}`;
const rootEl = ref(null);
const headerEl = ref(null);
const bodyEl = ref(null);
const contentEl = ref(null);
const contentHeight = ref(0);
const openHeight = ref(0);
const containerHeight = ref(0);
const headerHeight = ref(0);
const blockEndGap = ref(0);
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
  blockEndGap.value = Number.parseFloat(getComputedStyle(root).getPropertyValue('--preview-drawer-block-end-gap')) || 0;
  headerHeight.value = header.offsetHeight;
  const fullBody = contentEl.value?.offsetHeight || 0;
  contentHeight.value = headerHeight.value + 1 + fullBody;
  const boundary = props.expandBoundarySelector ? body.querySelector(props.expandBoundarySelector) : null;
  const bodyCut = boundary
    ? Math.max(0, Math.round(boundary.getBoundingClientRect().top - body.getBoundingClientRect().top + body.scrollTop))
    : fullBody;
  openHeight.value = headerHeight.value + 1 + bodyCut;
  updateScrollCue();
}
function scheduleMeasure() {
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(measureContent);
}
function observeLayout() {
  observer?.disconnect();
  observer = new ResizeObserver(scheduleMeasure);
  for (const el of [rootEl.value, headerEl.value, contentEl.value]) {
    if (el) observer.observe(el);
  }
  measureContent();
}
onMounted(observeLayout);
watch([headerEl, contentEl], () => { void nextTick(observeLayout); });
watch(() => props.isOpen, async open => {
  if (!open && bodyEl.value?.contains(document.activeElement)) {
    headerEl.value?.querySelector('[aria-expanded]')?.focus();
  }
  await nextTick();
  measureContent();
});
function cancelSwap() {
  swapAnimations.forEach(animation => animation.cancel());
  swapAnimations = [];
}
watch(() => props.contentKey, async () => {
  cancelSwap();
  await nextTick();
  if (bodyEl.value) bodyEl.value.scrollTop = 0;
  measureContent();
  if (!props.isOpen || rootEl.value?.closest('.pm-no-animations')
    || window.matchMedia('(prefers-reduced-motion: reduce)').matches
    || bodyEl.value?.contains(document.activeElement)) return;
  // Animate existing nodes; field instances and keyboard focus survive.
  for (const el of [headerEl.value?.querySelector('.details-drawer__title-wrap'), contentEl.value]) {
    if (el) swapAnimations.push(el.animate([
      { opacity: 0.25, transform: 'translateY(4px)' },
      { opacity: 1, transform: 'translateY(0)' }
    ], { duration: 220, easing: 'cubic-bezier(.16, 1, .3, 1)' }));
  }
});
const drawerStyle = computed(() => {
  if (!props.isOpen) return { height: `${props.collapsedHeight}px`, marginTop: `-${props.collapsedHeight}px` };
  const cap = Math.max(headerHeight.value, containerHeight.value - props.minViewerHeight - blockEndGap.value);
  const target = openHeight.value || contentHeight.value || props.collapsedHeight;
  const height = Math.round(Math.min(target, contentHeight.value || target, cap || props.collapsedHeight));
  return { height: `${height}px`, marginTop: '0px' };
});
onBeforeUnmount(() => {
  observer?.disconnect();
  cancelAnimationFrame(frame);
  cancelSwap();
});
</script>

<style scoped>
.preview-layout {
  --preview-drawer-block-end-gap: 0px;
  --preview-drawer-max-width: none;
  --preview-drawer-radius: 0px;
  --preview-drawer-width: 100%;
  --preview-drawer-card-bg: rgb(var(--v-theme-surface));
  --preview-drawer-card-hover-bg: rgb(var(--v-theme-surface));
  --preview-drawer-card-hover-border: rgb(var(--v-theme-primary) / 0.28);
  --preview-drawer-card-hover-ring: rgb(var(--v-theme-primary) / 0.08);
  --preview-drawer-collapsed-border: var(--pm-drawer-border-collapsed, rgb(var(--v-theme-on-surface) / 0.12));
  --preview-drawer-collapsed-shadow:
    0 18px 48px rgba(15, 23, 42, 0.18),
    0 2px 8px rgba(15, 23, 42, 0.08);
  --preview-drawer-motion-duration: 380ms;
  --preview-drawer-motion-easing: cubic-bezier(0.2, 1.08, 0.32, 1);
  --preview-drawer-scrim-rgb: 255, 255, 255;
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* Der Wrapper schließt den Bereich oberhalb des PDF-Viewers. Er muss
     dieselbe Stage-Farbe tragen wie die PDF-Seitenfläche, damit dort keine
     weiße App-Oberfläche sichtbar wird. */
  background: var(--pm-pdf-stage-bg, var(--pm-viewer-surface));
}

.preview-layout--floating-card {
  --preview-drawer-block-end-gap: 18px;
  --preview-drawer-card-bg: var(--pm-app-surface-raised);
  --preview-drawer-max-width: none;
  --preview-drawer-radius: 28px;
  --preview-drawer-width: min(600px, calc(100% - 64px));
}

.preview-layout--floating-card::after {
  content: '';
  position: absolute;
  inset-inline: 0;
  bottom: 0;
  z-index: 40;
  height: min(86%, 760px);
  pointer-events: none;
  opacity: 0;
  background:
    linear-gradient(
      to bottom,
      rgba(var(--preview-drawer-scrim-rgb), 0) 0%,
      rgba(var(--preview-drawer-scrim-rgb), 0.18) 18%,
      rgba(var(--preview-drawer-scrim-rgb), 0.74) 46%,
      rgba(var(--preview-drawer-scrim-rgb), 0.98) 100%
    );
  transition: opacity 360ms ease;
}

.preview-layout--floating-card.preview-layout--drawer-open::after {
  opacity: var(--preview-drawer-scrim-opacity, 1);
}

.preview-layout__viewer {
  flex: 1 1 auto;
  min-height: 0;
  position: relative;
  z-index: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--pm-pdf-stage-bg, var(--pm-viewer-surface));
}

.preview-layout__drawer {
  flex: 0 0 auto;
  position: relative;
  z-index: 50;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  width: var(--preview-drawer-width);
  max-width: var(--preview-drawer-max-width);
  margin-inline: auto;
  margin-bottom: var(--preview-drawer-block-end-gap);
  border-top: 1px solid var(--pm-drawer-border-collapsed, rgb(var(--v-theme-on-surface) / 0.12));
  border-radius: var(--preview-drawer-radius);
  transition:
    width var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing),
    border-radius var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing),
    translate 240ms var(--preview-drawer-motion-easing),
    height var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing) var(--preview-drawer-close-delay, 0ms),
    margin-top var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing) var(--preview-drawer-close-delay, 0ms),
    margin-bottom var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing),
    bottom var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing),
    background-color var(--pm-duration-normal) var(--pm-easing-decel),
    border-color var(--pm-duration-normal) var(--pm-easing-decel),
    box-shadow var(--pm-duration-normal) var(--pm-easing-decel),
    opacity var(--pm-duration-normal) var(--pm-easing-decel);

}

/* Der inhaltliche Zustand der Schublade bleibt erhalten; außerhalb der
   Vorschau wird nur ihre Darstellung ausgeblendet. Fokus hält sie sichtbar,
   damit Eingaben nicht während der Bearbeitung verschwinden. */
.preview-layout--drawer-auto-hide:not(:hover):not(:focus-within) .preview-layout__drawer {
  opacity: 0;
  pointer-events: none;
}

.preview-layout--floating-card .preview-layout__drawer {
  position: absolute;
  left: 50%;
  bottom: var(--preview-drawer-block-end-gap);
  margin-inline: 0;
  margin-bottom: 0;
  transform: translateX(-50%);
  border: 1px solid var(--preview-drawer-collapsed-border);
  box-shadow: var(--preview-drawer-collapsed-shadow);
}

.pm-drawer--expanded {
  background: var(--pm-drawer-bg-expanded, rgb(var(--v-theme-surface)));
  border-top-color: var(--pm-drawer-border-expanded, rgb(var(--v-theme-on-surface) / 0.16));
  box-shadow: 0 -4px 14px rgba(0, 0, 0, 0.08);
}

.preview-layout--floating-card .pm-drawer--expanded {
  background: var(--preview-drawer-card-bg);
  border-color: var(--pm-drawer-border-expanded, rgb(var(--v-theme-on-surface) / 0.16));
  opacity: 1;
}

.pm-drawer--collapsed {
  background: var(--pm-drawer-bg-collapsed, rgb(var(--v-theme-surface) / 0.6));
  border-top-color: var(--pm-drawer-border-collapsed, rgb(var(--v-theme-on-surface) / 0.12));
  /* Eingeklappt scheint das darunterliegende Dokument leicht durch (frosted). */
  backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  -webkit-backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.06);
}

.preview-layout--floating-card .pm-drawer--collapsed {
  background: var(--preview-drawer-card-bg);
  border-color: var(--preview-drawer-collapsed-border);
  box-shadow: var(--preview-drawer-collapsed-shadow);
  opacity: 1;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  cursor: pointer;
}

.preview-layout--floating-card .pm-drawer--collapsed:hover,
.preview-layout--floating-card .pm-drawer--collapsed:focus-within {
  background: var(--preview-drawer-card-hover-bg);
  border-color: var(--preview-drawer-card-hover-border);
  opacity: 1;
  box-shadow:
    0 18px 48px rgba(15, 23, 42, 0.2),
    0 2px 8px rgba(15, 23, 42, 0.1),
    0 0 0 3px var(--preview-drawer-card-hover-ring);
}

.preview-layout__header {
  flex: 0 0 auto;
  min-height: 56px;
}

.pm-drawer-divider {
  width: 100%;
  height: 1px;
  opacity: 0;
  background: rgba(var(--v-theme-on-surface), 0.08);
  transition: opacity var(--pm-duration-fast) var(--pm-easing-decel);
}

.pm-drawer-divider--visible {
  opacity: 1;
}

.preview-layout__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  opacity: 0;
  transition: opacity var(--pm-duration-fast) var(--pm-easing-decel);
}

.preview-layout__body--open {
  opacity: 1;
  overflow-y: auto;
}

.preview-layout__body--closed {
  pointer-events: none;
}

.pm-drawer :deep(:focus) {
  outline: none;
}

.pm-drawer :deep(:focus-visible) {
  outline: 2px solid rgba(var(--v-theme-primary), 0.25);
  outline-offset: 2px;
  border-radius: 10px;
}

@media (max-width: 900px) {
  .preview-layout--floating-card {
    --preview-drawer-block-end-gap: 12px;
    --preview-drawer-radius: 22px;
    --preview-drawer-width: calc(100% - 32px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .preview-layout {
    --preview-drawer-motion-duration: 120ms;
    --preview-drawer-motion-easing: ease-out;
  }
}


/* Contents follow the shell on opening and fade before closing. */
.preview-layout:not(.preview-layout--drawer-open) { --preview-drawer-close-delay: 65ms; }
.preview-layout__body { transition: opacity 70ms ease; }
.preview-layout__body--open { transition: opacity 160ms ease 70ms; }
.preview-layout__body :deep(.pm-metadata-row) {
  opacity: 0; transform: translateY(5px);
  transition: opacity 65ms ease, transform 65ms ease;
}
.preview-layout__body--open :deep(.pm-metadata-row) {
  opacity: 1; transform: translateY(0);
  transition: opacity 180ms ease var(--field-enter-delay, 80ms), transform 220ms cubic-bezier(.16, 1, .3, 1) var(--field-enter-delay, 80ms);
}
.preview-layout__body :deep(.pm-metadata-row:nth-child(2)) { --field-enter-delay: 100ms; }
.preview-layout__body :deep(.pm-metadata-row:nth-child(3)) { --field-enter-delay: 120ms; }
.preview-layout__body :deep(.pm-metadata-row:nth-child(4)) { --field-enter-delay: 140ms; }
.preview-layout__body :deep(.pm-metadata-row:nth-child(5)) { --field-enter-delay: 160ms; }
:global(.pm-no-animations) .preview-layout__drawer,
:global(.pm-no-animations) .preview-layout__body,
:global(.pm-no-animations) .preview-layout__body :deep(.pm-metadata-row) { transition: none; }
:global(.pm-no-animations) .preview-layout__body :deep(.pm-metadata-row) { transform: none; }
@media (prefers-reduced-motion: reduce) {
  .preview-layout__drawer, .preview-layout__body,
  .preview-layout__body :deep(.pm-metadata-row) { transition: none; }
  .preview-layout__body :deep(.pm-metadata-row) { transform: none; }
}


/* The compact dock unfolds into a broader work surface. */
.preview-layout--floating-card.preview-layout--drawer-open {
  --preview-drawer-width: min(760px, calc(100% - 32px));
  --preview-drawer-radius: 24px;
}
.preview-layout--floating-card .pm-drawer--expanded {
  box-shadow: 0 28px 72px rgb(0 0 0 / .22), 0 6px 18px rgb(0 0 0 / .1);
}
.preview-layout--floating-card .preview-layout__header {
  position: relative;
  z-index: 2;
  background: linear-gradient(145deg, color-mix(in srgb, var(--pm-accent, #006b75) 4%, var(--preview-drawer-card-bg)), var(--preview-drawer-card-bg));
}
.preview-layout__handle {
  position: absolute;
  inset: 6px 0 auto;
  display: flex;
  justify-content: center;
  z-index: 3;
  pointer-events: none;
}
.preview-layout__handle span {
  width: 28px; height: 3px; border-radius: 3px;
  background: color-mix(in srgb, var(--pm-text, #526067) 18%, transparent);
  transition: width 320ms ease, background-color 240ms ease;
}
.preview-layout--drawer-open .preview-layout__handle span { width: 40px; }
@media (hover: hover) and (pointer: fine) {
  .preview-layout--floating-card .pm-drawer--collapsed:hover { translate: 0 -2px; }
  .preview-layout--floating-card .pm-drawer--collapsed:hover .preview-layout__handle span {
    background: color-mix(in srgb, var(--pm-accent, #006b75) 50%, transparent);
    width: 36px;
  }
}
.preview-layout__content { display: flow-root; min-width: 0; }
.preview-layout__scroll-cue {
  position: absolute;
  bottom: 0; inset-inline: 0; height: 30px;
  z-index: 3; pointer-events: none; opacity: 0;
  background: linear-gradient(transparent, var(--preview-drawer-card-bg));
  transition: opacity 180ms ease;
}
.preview-layout__scroll-cue--visible { opacity: 1; }
:global(.pm-no-animations) .preview-layout__handle span,
:global(.pm-no-animations) .preview-layout__scroll-cue { transition: none; }
:global(.pm-no-animations) .preview-layout__drawer { translate: none; }
@media (prefers-reduced-motion: reduce) {
  .preview-layout__handle span, .preview-layout__scroll-cue { transition: none; }
  .preview-layout__drawer { translate: none !important; }
}
/* Keep theme-specific drawer selectors in global style.css to avoid scoped selector leaks. */
</style>
