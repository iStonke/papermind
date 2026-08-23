<template>
  <v-list-item
    ref="rootRef"
    class="sidebar-item pm-nav-item"
    :class="[itemClass, { 'sidebar-item--pulse': isPulseActive }]"
    :active="active"
    @click="$emit('click', $event)"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
    @focusin="hasFocusWithin = true"
    @focusout="onFocusOut"
  >
    <template #prepend>
      <slot name="icon" />
    </template>

    <v-list-item-title :class="labelClass">
      <slot />
    </v-list-item-title>

    <template #append>
      <div v-if="reserveRight" class="sidebar-item-right">
        <span v-if="showCount" class="sidebar-item-count" :class="countClass">{{ count }}</span>
        <div
          v-if="hasAction"
          class="sidebar-item-action"
          :class="{ 'sidebar-item-action--visible': isActionVisible }"
        >
          <slot name="action" />
        </div>
      </div>
      <slot v-else name="append" />
    </template>
  </v-list-item>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, useSlots, watch } from 'vue';

const props = defineProps({
  active: {
    type: Boolean,
    default: false
  },
  itemClass: {
    type: [String, Array, Object],
    default: ''
  },
  labelClass: {
    type: [String, Array, Object],
    default: ''
  },
  countClass: {
    type: [String, Array, Object],
    default: ''
  },
  count: {
    type: [String, Number],
    default: null
  },
  reserveRight: {
    type: Boolean,
    default: true
  },
  actionMode: {
    type: String,
    default: 'never'
  },
  pulseKey: {
    type: Number,
    default: 0
  }
});

defineEmits(['click']);

const slots = useSlots();
const rootRef = ref(null);
const isHovered = ref(false);
const hasFocusWithin = ref(false);
const isPulseActive = ref(false);
let pulseTimer = null;
let pulseGeneration = 0;

watch(
  () => props.pulseKey,
  (nextKey, previousKey) => {
    if (nextKey === previousKey || nextKey <= 0) return;
    const generation = ++pulseGeneration;
    if (pulseTimer) window.clearTimeout(pulseTimer);
    isPulseActive.value = false;
    void nextTick(() => {
      if (generation !== pulseGeneration) return;
      // Layout einmal lesen, damit auch zwei kurz aufeinanderfolgende Impulse
      // zuverlässig als neue CSS-Animation starten.
      void resolveRootElement()?.offsetWidth;
      isPulseActive.value = true;
      pulseTimer = window.setTimeout(() => {
        if (generation === pulseGeneration) isPulseActive.value = false;
        pulseTimer = null;
      }, 760);
    });
  }
);

onBeforeUnmount(() => {
  pulseGeneration += 1;
  if (pulseTimer) window.clearTimeout(pulseTimer);
});

function resolveRootElement() {
  const candidate = rootRef.value;
  return candidate?.$el instanceof HTMLElement ? candidate.$el : candidate;
}

// Flugziel für globale Übergänge: Die Miniatur verschwindet optisch im Icon,
// nicht irgendwo in der gesamten Zeilenfläche. Das funktioniert ebenso im Rail.
function getFlightTarget() {
  const root = resolveRootElement();
  if (!(root instanceof HTMLElement)) return null;
  const iconSlot = root.querySelector('.v-list-item__prepend');
  const destination = iconSlot instanceof HTMLElement ? iconSlot : root;
  const rect = destination.getBoundingClientRect();
  if (rect.width < 2 || rect.height < 2) return null;
  const style = window.getComputedStyle(destination);
  const borderRadius = Number.parseFloat(style.borderTopLeftRadius || '0');
  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
    borderRadius: Number.isFinite(borderRadius) ? borderRadius : 0,
    borderWidth: 0,
    vanish: true
  };
}

defineExpose({ getFlightTarget });

const hasAction = computed(() => Boolean(slots.action));
const showCount = computed(() => props.count !== null && props.count !== undefined && props.count !== '');

function onFocusOut(event) {
  const nextFocused = event.relatedTarget;
  if (!event.currentTarget?.contains(nextFocused)) {
    hasFocusWithin.value = false;
  }
}

const isActionVisible = computed(() => {
  if (!hasAction.value) {
    return false;
  }
  if (props.actionMode === 'always') {
    return true;
  }
  if (props.actionMode === 'active') {
    return props.active || hasFocusWithin.value;
  }
  if (props.actionMode === 'hover-active') {
    return props.active || isHovered.value || hasFocusWithin.value;
  }
  return false;
});
</script>

<style scoped>
.sidebar-item {
  --pm-sidebar-right-width: 24px;
  border-inline-start: none !important;
}

.sidebar-item :deep(.v-list-item__content) {
  min-width: 0;
}

.sidebar-item :deep(.v-list-item-title) {
  min-width: 0;
  overflow: hidden;
}

.sidebar-item-right {
  position: relative;
  width: var(--pm-sidebar-right-width);
  min-width: var(--pm-sidebar-right-width);
  display: inline-flex;
  justify-content: flex-end;
  align-items: center;
}

.sidebar-item-count {
  min-width: 2ch;
  text-align: right;
  font-size: 0.78rem;
  font-weight: 600;
  opacity: var(--pm-sidebar-count-opacity, 0.68);
  font-variant-numeric: tabular-nums;
}

.sidebar-item-action {
  position: absolute;
  top: 50%;
  right: 10px;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity var(--pm-duration-fast, 140ms) var(--pm-easing, cubic-bezier(0.4, 0, 0.2, 1));
}

.sidebar-item-action--visible {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
}

/* Aktiver Eintrag: fett */
.sidebar-item.v-list-item--active :deep(.v-list-item-title) {
  font-weight: 600;
}

.sidebar-item--pulse::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  border: 1px solid color-mix(in srgb, var(--pm-accent) 55%, transparent);
  border-radius: inherit;
  background: color-mix(in srgb, var(--pm-accent) 14%, transparent);
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--pm-accent) 28%, transparent);
  opacity: 0;
  pointer-events: none;
  animation: sidebar-item-import-pulse 720ms cubic-bezier(0.22, 0.72, 0.24, 1) both;
}

.sidebar-item--pulse :deep(.v-icon) {
  animation: sidebar-item-import-icon-pulse 720ms cubic-bezier(0.22, 0.72, 0.24, 1) both;
}

@keyframes sidebar-item-import-pulse {
  0%   { opacity: 0; transform: scale(0.96); }
  28%  { opacity: 1; transform: scale(1); box-shadow: 0 0 0 3px color-mix(in srgb, var(--pm-accent) 13%, transparent); }
  62%  { opacity: 0.52; transform: scale(1); }
  100% { opacity: 0; transform: scale(1.015); box-shadow: 0 0 0 7px transparent; }
}

@keyframes sidebar-item-import-icon-pulse {
  0%, 100% { transform: scale(1); }
  34%      { transform: scale(1.16); }
}

:global(.pm-no-animations) .sidebar-item--pulse::after,
:global(.pm-no-animations) .sidebar-item--pulse :deep(.v-icon) {
  animation: none;
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-item--pulse::after,
  .sidebar-item--pulse :deep(.v-icon) {
    animation: none;
  }
}
</style>
