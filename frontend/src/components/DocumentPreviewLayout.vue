<template>
  <div ref="rootEl" class="preview-layout">
    <div class="preview-layout__viewer">
      <slot name="viewer" />
    </div>

    <section
      v-if="showDrawer"
      :class="[
        'preview-layout__drawer',
        'pm-drawer',
        isOpen ? 'pm-drawer--expanded' : 'pm-drawer--collapsed',
        { 'pm-drawer--dragging': isDragging }
      ]"
      :style="drawerStyle"
      role="region"
      aria-label="Dokumentdetails"
    >
      <div
        v-if="isOpen"
        class="preview-layout__splitter"
        role="separator"
        aria-orientation="horizontal"
        aria-label="Höhe des Detailbereichs anpassen"
        tabindex="0"
        @pointerdown="startDrag"
        @pointermove="onDrag"
        @pointerup="endDrag"
        @pointercancel="endDrag"
        @keydown="onSplitterKey"
        @dblclick="resetHeight"
      >
        <span class="preview-layout__grip" aria-hidden="true" />
      </div>

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
import { computed, onBeforeUnmount, ref, watch } from 'vue';

const props = defineProps({
  showDrawer: { type: Boolean, default: false },
  isOpen: { type: Boolean, default: false },
  collapsedHeight: { type: Number, default: 72 },
  expandedHeight: { type: Number, default: 320 },
  minExpandedHeight: { type: Number, default: 180 },
  minViewerHeight: { type: Number, default: 140 },
  defaultExpandedHeight: { type: Number, default: 320 }
});

const emit = defineEmits(['update:expandedHeight']);

const SPLITTER_HEIGHT = 12;
const DIVIDER_HEIGHT = 1;

const rootEl = ref(null);
const headerEl = ref(null);
const bodyEl = ref(null);
const isDragging = ref(false);

// Natürliche Höhe von Kopfzeile + Formular – darüber hinaus entsteht nur Leerraum.
const contentHeight = ref(0);

function measureContent() {
  const header = headerEl.value?.offsetHeight || 0;
  const body = bodyEl.value?.scrollHeight || 0;
  contentHeight.value = header + body + SPLITTER_HEIGHT + DIVIDER_HEIGHT;
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
onBeforeUnmount(() => contentObserver?.disconnect());

// Deckel: nie höher als der Inhalt (kein Leerraum) und nie höher als der Container
// abzüglich der Mindesthöhe des Viewers (bei langem Inhalt scrollt der Body).
function maxAllowedHeight() {
  const root = rootEl.value;
  const containerCap = root
    ? root.getBoundingClientRect().height - props.minViewerHeight
    : Infinity;
  const contentCap = contentHeight.value || Infinity;
  return Math.max(props.minExpandedHeight, Math.min(containerCap, contentCap));
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
  const cap = contentHeight.value
    ? Math.min(props.expandedHeight, contentHeight.value)
    : props.expandedHeight;
  return { height: `${cap}px`, marginTop: '0px' };
});

function clampHeight(value) {
  const upperBound = maxAllowedHeight();
  return Math.round(Math.min(Math.max(value, props.minExpandedHeight), upperBound));
}

function startDrag(event) {
  if (!props.isOpen) return;
  isDragging.value = true;
  event.currentTarget.setPointerCapture?.(event.pointerId);
  event.preventDefault();
}

function onDrag(event) {
  if (!isDragging.value || !rootEl.value) return;
  const rect = rootEl.value.getBoundingClientRect();
  emit('update:expandedHeight', clampHeight(rect.bottom - event.clientY));
}

function endDrag(event) {
  if (!isDragging.value) return;
  isDragging.value = false;
  event.currentTarget.releasePointerCapture?.(event.pointerId);
}

function onSplitterKey(event) {
  const step = event.shiftKey ? 48 : 16;
  if (event.key === 'ArrowUp') {
    emit('update:expandedHeight', clampHeight(props.expandedHeight + step));
    event.preventDefault();
  } else if (event.key === 'ArrowDown') {
    emit('update:expandedHeight', clampHeight(props.expandedHeight - step));
    event.preventDefault();
  }
}

function resetHeight() {
  emit('update:expandedHeight', clampHeight(props.defaultExpandedHeight));
}
</script>

<style scoped>
.preview-layout {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-layout__viewer {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-layout__drawer {
  flex: 0 0 auto;
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-top: 1px solid var(--pm-drawer-border-collapsed, rgb(var(--v-theme-on-surface) / 0.12));
  transition:
    height 200ms ease-out,
    margin-top 200ms ease-out,
    background-color 200ms ease-out,
    border-color 200ms ease-out;
  will-change: height, margin-top;
}

.pm-drawer--dragging {
  transition: none;
}

.pm-drawer--expanded {
  background: var(--pm-drawer-bg-expanded, rgb(var(--v-theme-surface)));
  border-top-color: var(--pm-drawer-border-expanded, rgb(var(--v-theme-on-surface) / 0.16));
  box-shadow: 0 -4px 14px rgba(0, 0, 0, 0.08);
}

.pm-drawer--collapsed {
  background: var(--pm-drawer-bg-collapsed, rgb(var(--v-theme-surface) / 0.6));
  border-top-color: var(--pm-drawer-border-collapsed, rgb(var(--v-theme-on-surface) / 0.12));
  /* Eingeklappt scheint das darunterliegende Dokument leicht durch (frosted). */
  backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  -webkit-backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 11px)) saturate(1.05);
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.06);
}

.preview-layout__splitter {
  flex: 0 0 auto;
  height: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: ns-resize;
  touch-action: none;
  user-select: none;
}

.preview-layout__splitter:hover .preview-layout__grip,
.preview-layout__splitter:focus-visible .preview-layout__grip {
  background: rgba(var(--v-theme-primary), 0.55);
  width: 40px;
}

.preview-layout__splitter:focus-visible {
  outline: none;
}

.preview-layout__grip {
  width: 32px;
  height: 4px;
  border-radius: 2px;
  background: rgba(var(--v-theme-on-surface), 0.22);
  transition: background-color 160ms ease, width 160ms ease;
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

/* Keep theme-specific drawer selectors in global style.css to avoid scoped selector leaks. */
</style>
