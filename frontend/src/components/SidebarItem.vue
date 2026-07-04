<template>
  <v-list-item
    class="sidebar-item pm-nav-item"
    :class="itemClass"
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
import { computed, ref, useSlots } from 'vue';

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
  }
});

defineEmits(['click']);

const slots = useSlots();
const isHovered = ref(false);
const hasFocusWithin = ref(false);

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
</style>
