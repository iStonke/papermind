<template>
  <div
    ref="rootEl"
    class="preview-layout"
    :class="{
      'preview-layout--floating-card': floatingCard,
      'preview-layout--drawer-open': showDrawer && isOpen
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

      <div class="pm-drawer-divider" :class="{ 'pm-drawer-divider--visible': isOpen }" aria-hidden="true" />

      <div
        ref="bodyEl"
        class="preview-layout__body"
        :class="isOpen ? 'preview-layout__body--open' : 'preview-layout__body--closed'"
        :aria-hidden="String(!isOpen)"
      >
        <slot name="drawer-body" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

const props = defineProps({
  showDrawer: { type: Boolean, default: false },
  isOpen: { type: Boolean, default: false },
  floatingCard: { type: Boolean, default: false },
  collapsedHeight: { type: Number, default: 72 },
  minViewerHeight: { type: Number, default: 140 },
  // Beim Ausklappen wird bis zur Oberkante dieses Elements aufgeklappt; alles
  // darunter (z. B. Notizen) bleibt verdeckt und nur per Scrollen erreichbar.
  expandBoundarySelector: { type: String, default: '[data-drawer-expand-boundary]' }
});

const DIVIDER_HEIGHT = 1;

const rootEl = ref(null);
const headerEl = ref(null);
const bodyEl = ref(null);

// Natürliche Höhe von Kopfzeile + kompletter Feldliste.
const contentHeight = ref(0);
// Ausklapphöhe bis zur Grenze (Kopf + Trennlinie + Body bis zur Boundary).
const openHeight = ref(0);

function measureContent() {
  const header = headerEl.value?.offsetHeight || 0;
  const body = bodyEl.value;
  if (!body) {
    contentHeight.value = 0;
    openHeight.value = 0;
    return;
  }
  const fullBody = body.scrollHeight;
  contentHeight.value = header + DIVIDER_HEIGHT + fullBody;

  // Body-Höhe bis zur Boundary (scroll-unabhängig über getBoundingClientRect).
  let bodyCut = fullBody;
  const boundary = props.expandBoundarySelector
    ? body.querySelector(props.expandBoundarySelector)
    : null;
  if (boundary) {
    const bodyTop = body.getBoundingClientRect().top;
    const boundaryTop = boundary.getBoundingClientRect().top;
    bodyCut = Math.max(0, Math.round(boundaryTop - bodyTop + body.scrollTop));
  }
  openHeight.value = header + DIVIDER_HEIGHT + bodyCut;
}

let contentObserver = null;
watch(bodyEl, (el) => {
  contentObserver?.disconnect();
  if (!el) return;
  contentObserver = new ResizeObserver(measureContent);
  contentObserver.observe(el);
  if (headerEl.value) contentObserver.observe(headerEl.value);
  measureContent();
});

// Nach dem Auf-/Zuklappen neu messen (Body wechselt zwischen Höhe 0 und auto).
watch(
  () => props.isOpen,
  async () => {
    await nextTick();
    measureContent();
  }
);

onBeforeUnmount(() => contentObserver?.disconnect());

// Deckel: nie höher als der Inhalt (kein Leerraum) und nie höher als der
// Container abzüglich der Mindesthöhe des Viewers (dann scrollt der Body).
function maxAllowedHeight() {
  const root = rootEl.value;
  const blockEndGap = root
    ? Number.parseFloat(getComputedStyle(root).getPropertyValue('--preview-drawer-block-end-gap')) || 0
    : 0;
  const containerCap = root
    ? root.getBoundingClientRect().height - props.minViewerHeight - blockEndGap
    : Infinity;
  const contentCap = contentHeight.value || Infinity;
  return Math.min(containerCap, contentCap);
}

const drawerStyle = computed(() => {
  if (!props.isOpen) {
    // Negativer Margin = die eingeklappte Leiste greift über den unteren
    // Viewer-Rand, statt darunter anzudocken. So scheint das Dokument durch die
    // durchscheinende Leiste hindurch; der Viewer behält die volle Höhe.
    return {
      height: `${props.collapsedHeight}px`,
      marginTop: `-${props.collapsedHeight}px`
    };
  }
  const target = openHeight.value || contentHeight.value;
  const cap = Math.round(Math.min(target, maxAllowedHeight()));
  return { height: `${cap}px`, marginTop: '0px' };
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
  --preview-drawer-motion-duration: 260ms;
  --preview-drawer-motion-easing: cubic-bezier(0.2, 1.28, 0.34, 1);
  --preview-drawer-scrim-rgb: 255, 255, 255;
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-layout--floating-card {
  --preview-drawer-block-end-gap: 18px;
  --preview-drawer-card-bg: #ffffff;
  --preview-drawer-max-width: none;
  --preview-drawer-radius: 28px;
  --preview-drawer-width: min(520px, calc(100% - 220px));
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
  transition: opacity 180ms ease-out;
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
    height var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing),
    margin-top var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing),
    margin-bottom var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing),
    bottom var(--preview-drawer-motion-duration) var(--preview-drawer-motion-easing),
    background-color 200ms ease-out,
    border-color 200ms ease-out,
    box-shadow 200ms ease-out,
    opacity 200ms ease-out;
  will-change: height, margin-top, margin-bottom, bottom;
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
  transition: opacity 160ms ease-out;
}

.pm-drawer-divider--visible {
  opacity: 1;
}

.preview-layout__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  opacity: 0;
  transition: opacity 160ms ease-out;
}

.preview-layout__body--open {
  opacity: 1;
  overflow-y: auto;
}

.preview-layout__body--closed {
  flex: 0 0 auto;
  height: 0;
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
    --preview-drawer-width: calc(100% - 24px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .preview-layout {
    --preview-drawer-motion-duration: 120ms;
    --preview-drawer-motion-easing: ease-out;
  }
}

/* Keep theme-specific drawer selectors in global style.css to avoid scoped selector leaks. */
</style>
