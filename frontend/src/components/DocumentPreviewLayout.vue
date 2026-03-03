<template>
  <div class="preview-layout">
    <div class="preview-layout__viewer">
      <slot name="viewer" />
    </div>

    <div
      v-if="showDrawer && isOpen"
      class="preview-layout__scrim"
      aria-hidden="true"
    />

    <section
      v-if="showDrawer"
      :class="[
        'preview-layout__drawer',
        'pm-drawer',
        isOpen ? 'preview-layout__drawer--open pm-drawer--expanded' : 'preview-layout__drawer--closed pm-drawer--collapsed'
      ]"
      :style="drawerStyle"
      role="dialog"
      aria-label="Dokumentdetails"
    >
      <div class="preview-layout__header">
        <slot name="drawer-header" />
      </div>

      <div class="pm-drawer-divider" :class="{ 'pm-drawer-divider--visible': isOpen }" aria-hidden="true" />

      <div
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
import { computed } from 'vue';

const props = defineProps({
  showDrawer: { type: Boolean, default: false },
  isOpen: { type: Boolean, default: false },
  collapsedHeight: { type: Number, default: 64 }
});

const drawerStyle = computed(() => ({
  maxHeight: props.isOpen ? '40vh' : `${props.collapsedHeight}px`
}));
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
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-layout__scrim {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: var(--pm-drawer-scrim, rgba(0, 0, 0, 0.08));
  z-index: 3;
}

.preview-layout__drawer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 18px;
  z-index: 4;
  width: min(680px, calc(100% - 48px));
  margin: 0 auto;
  border-radius: 14px;
  border: 1px solid transparent;
  overflow: hidden;
  transition:
    max-height 320ms ease-in-out,
    transform 320ms ease-in-out,
    background-color 320ms ease-in-out,
    border-color 320ms ease-in-out,
    backdrop-filter 320ms ease-in-out,
    box-shadow 320ms ease-in-out;
  display: flex;
  flex-direction: column;
}

.pm-drawer--expanded {
  transform: translateY(0);
  background: var(--pm-drawer-bg-expanded, rgb(var(--v-theme-surface)));
  border-color: var(--pm-drawer-border-expanded, rgb(var(--v-theme-on-surface) / 0.16));
  backdrop-filter: blur(var(--pm-drawer-blur-expanded, 5px));
  -webkit-backdrop-filter: blur(var(--pm-drawer-blur-expanded, 5px));
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

.pm-drawer--collapsed {
  transform: translateY(8px);
  background: var(--pm-drawer-bg-collapsed, rgb(var(--v-theme-surface) / 0.6));
  backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 12px));
  -webkit-backdrop-filter: blur(var(--pm-drawer-blur-collapsed, 12px));
  border-color: var(--pm-drawer-border-collapsed, rgb(var(--v-theme-on-surface) / 0.12));
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.preview-layout__header {
  flex: 0 0 auto;
  min-height: 60px;
}

.pm-drawer-divider {
  width: 100%;
  height: 1px;
  opacity: 0;
  background: rgba(var(--v-theme-on-surface), 0.08);
  transition: opacity 320ms ease-in-out;
}

.pm-drawer-divider--visible {
  opacity: 1;
}

.preview-layout__body {
  flex: 0 1 auto;
  min-height: 0;
  overflow: hidden;
  max-height: 0;
  opacity: 0;
  transition:
    max-height 320ms ease-in-out,
    opacity 320ms ease-in-out;
}

.preview-layout__body--open {
  flex: 1 1 auto;
  max-height: 60vh;
  opacity: 1;
}

.preview-layout__body--closed {
  pointer-events: none;
}

.preview-layout__body--open {
  overflow-y: auto;
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

@media (max-width: 900px) {
  .preview-layout__drawer {
    width: min(620px, calc(100% - 20px));
    bottom: 12px;
    border-radius: 12px;
  }
}
</style>
