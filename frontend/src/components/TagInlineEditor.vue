<template>
  <div class="pm-tags-input" :class="{ 'pm-tags-input--disabled': disabled }">
    <TransitionGroup name="metadata-tag-chip" tag="div" class="pm-tags-input__chips">
      <span
        v-for="name in normalizedNames"
        :key="name"
        class="pm-tags-input__chip-wrap"
      >
        <v-chip
          size="small"
          closable
          class="pm-tags-input__chip"
          @click:close="emit('remove', name)"
        >
          {{ name }}
        </v-chip>
      </span>
    </TransitionGroup>

    <v-combobox
      :model-value="normalizedNames"
      :search="search"
      :items="items"
      multiple
      hide-selected
      no-filter
      :clearable="false"
      density="compact"
      variant="plain"
      hide-details
      class="pm-tags-input__field"
      menu-icon=""
      :loading="loading"
      :disabled="disabled"
      :menu-props="resolvedMenuProps"
      @update:model-value="emit('update:modelValue', $event)"
      @update:search="emit('update:search', $event || '')"
      @keydown.capture="emit('keydown', $event)"
      @focus="emit('focus', $event)"
    >
      <template #selection></template>
      <template #item="{ props: itemProps, item }">
        <v-list-item
          v-bind="itemProps"
          :class="{ 'pm-tags-input__menu-item--active': isItemActive?.(item) }"
        />
      </template>
      <template #prepend-inner>
        <span class="pm-tags-input__add">
          <v-icon size="14" class="pm-tags-input__plus">mdi-plus</v-icon>
          <span class="pm-tags-input__add-label">Tag</span>
        </span>
      </template>
    </v-combobox>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  search: { type: String, default: '' },
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  menuProps: { type: Object, default: () => ({}) },
  isItemActive: { type: Function, default: null },
});

const emit = defineEmits([
  'update:modelValue',
  'update:search',
  'remove',
  'keydown',
  'focus',
]);

const normalizedNames = computed(() => {
  const seen = new Set();
  const names = [];
  for (const value of props.modelValue || []) {
    const name = String(value?.title ?? value?.name ?? value ?? '').replace(/\s+/g, ' ').trim();
    const key = name.toLocaleLowerCase('de-DE');
    if (name && !seen.has(key)) {
      seen.add(key);
      names.push(name);
    }
  }
  return names;
});

const resolvedMenuProps = computed(() => ({
  location: 'top start',
  origin: 'bottom start',
  offset: 10,
  maxHeight: 180,
  closeOnContentClick: false,
  contentClass: 'pm-menu pm-menu--tags pm-tag-inline-menu',
  ...props.menuProps,
}));
</script>

<style scoped>
.pm-tags-input {
  --pm-detail-chip-bg: var(--pm-chip-bg, rgba(var(--v-theme-on-surface), 0.06));
  --pm-detail-chip-border: color-mix(in srgb, var(--pm-chip-text, var(--pm-text)) 14%, transparent);
  --pm-detail-chip-close-color: var(--pm-chip-count, var(--pm-muted));
  --pm-detail-chip-add-border: color-mix(in srgb, var(--pm-muted) 55%, transparent);
  --pm-detail-field-hover-border: color-mix(in srgb, var(--pm-divider) 55%, var(--pm-text));
  display: flex;
  min-width: 0;
  min-height: 34px;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  padding: 2px 0;
}

.pm-tags-input__chips {
  display: flex;
  min-width: 0;
  flex: 0 1 auto;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
}

.pm-tags-input--disabled {
  opacity: 0.6;
  pointer-events: none;
}

.pm-tags-input__chip.v-chip {
  height: 26px !important;
  max-width: min(220px, 100%);
  border: 1px solid var(--pm-detail-chip-border) !important;
  border-radius: 15px !important;
  background: var(--pm-detail-chip-bg) !important;
  color: rgba(var(--v-theme-on-surface), 0.88) !important;
  font-size: 12.5px !important;
  padding-inline: 11px 7px !important;
  transition:
    background-color var(--pm-duration-fast, 140ms) ease,
    border-color var(--pm-duration-fast, 140ms) ease,
    color var(--pm-duration-fast, 140ms) ease,
    box-shadow var(--pm-duration-fast, 140ms) ease,
    transform var(--pm-duration-fast, 140ms) ease !important;
}

.pm-tags-input__chip.v-chip:hover {
  border-color: color-mix(in srgb, var(--pm-detail-chip-close-color) 44%, transparent) !important;
  box-shadow: 0 3px 8px rgba(15, 23, 42, 0.1);
  transform: translateY(-1px);
}

.pm-tags-input__chip :deep(.v-chip__underlay),
.pm-tags-input__chip :deep(.v-chip__overlay) {
  opacity: 0 !important;
  background: transparent !important;
}

.pm-tags-input__chip :deep(.v-chip__close) {
  width: 18px !important;
  height: 18px !important;
  margin-inline-start: 5px !important;
  border-radius: 999px !important;
  background: transparent !important;
  color: var(--pm-detail-chip-close-color) !important;
  font-size: 16px !important;
  opacity: 1 !important;
}

.pm-tags-input__chip :deep(.v-chip__close:hover) {
  color: rgb(var(--v-theme-on-surface)) !important;
}

.pm-tags-input__chip-wrap {
  display: inline-flex;
}

.pm-tags-input__chip-wrap.metadata-tag-chip-enter-active,
.pm-tags-input__chip-wrap.metadata-tag-chip-leave-active {
  will-change: opacity, transform;
}

.pm-tags-input__chip-wrap.metadata-tag-chip-enter-active {
  animation: metadata-tag-chip-in var(--pm-tag-chip-enter-duration, 320ms) cubic-bezier(0.22, 1.25, 0.36, 1) both;
}

.pm-tags-input__chip-wrap.metadata-tag-chip-leave-active {
  animation: metadata-tag-chip-out var(--pm-tag-chip-leave-duration, 200ms) ease-in both;
}

.metadata-tag-chip-move {
  transition: transform var(--pm-duration-fast, 140ms) cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes metadata-tag-chip-in {
  from { opacity: 0; transform: translateY(8px) scale(0.72); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes metadata-tag-chip-out {
  from { opacity: 1; transform: translateY(0) scale(1); }
  to { opacity: 0; transform: translateY(-5px) scale(0.78); }
}

.pm-tags-input__field.v-input {
  position: relative;
  width: auto;
  min-height: 26px !important;
  height: 26px !important;
  flex: 0 0 auto;
  border: none;
  border-radius: 15px;
  padding: 0 11px 0 9px;
  --v-input-control-height: 26px !important;
}

.pm-tags-input__field.v-input::before,
.pm-tags-input__field.v-input::after {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  content: '';
  transition: opacity 0.18s ease, border-color 0.12s ease;
}

.pm-tags-input__field.v-input::before {
  border: 1px dashed var(--pm-detail-chip-add-border);
}

.pm-tags-input__field.v-input:hover::before {
  border-color: var(--pm-detail-field-hover-border);
}

.pm-tags-input__field.v-input::after {
  border: 1px solid rgba(var(--v-theme-primary), 0.6);
  opacity: 0;
}

.pm-tags-input__field.v-input--focused::before { opacity: 0; }
.pm-tags-input__field.v-input--focused::after { opacity: 1; }

.pm-tags-input__add {
  display: inline-flex;
  align-items: center;
  color: rgba(var(--v-theme-on-surface), 0.6);
  white-space: nowrap;
}

.pm-tags-input__plus { color: inherit; }

.pm-tags-input__add-label {
  max-width: 3.5em;
  margin-left: 4px;
  overflow: hidden;
  font-size: 12.5px;
  opacity: 1;
  transition: max-width 0.18s ease, opacity 0.18s ease, margin-left 0.18s ease;
}

.pm-tags-input__field.v-input--focused .pm-tags-input__add-label {
  max-width: 0;
  margin-left: 0;
  opacity: 0;
}

.pm-tags-input__field :deep(.v-field__input) {
  width: 0;
  min-width: 0 !important;
  height: 26px !important;
  min-height: 26px !important;
  flex: 0 0 auto;
  align-items: center !important;
  padding: 0 !important;
  font-size: 0.85rem;
  transition: width 0.18s ease;
}

.pm-tags-input__field.v-input--focused :deep(.v-field__input) {
  width: 104px;
}

.pm-tags-input__field :deep(.v-input__control),
.pm-tags-input__field :deep(.v-field),
.pm-tags-input__field :deep(.v-field__field),
.pm-tags-input__field :deep(.v-field__prepend-inner),
.pm-tags-input__field :deep(.v-field__append-inner) {
  min-height: 26px !important;
  height: 26px !important;
}

.pm-tags-input__field :deep(.v-field) {
  padding: 0;
  --v-field-padding-start: 0;
  --v-field-padding-end: 0;
}

.pm-tags-input__field :deep(.v-field__field),
.pm-tags-input__field :deep(.v-field__prepend-inner) {
  align-items: center !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

.pm-tags-input__field :deep(.v-field__prepend-inner) {
  padding-inline-end: 5px !important;
}

.pm-tags-input__field :deep(.v-field__append-inner) {
  padding: 0 !important;
}

@media (prefers-reduced-motion: reduce) {
  .pm-tags-input__chip-wrap.metadata-tag-chip-enter-active,
  .pm-tags-input__chip-wrap.metadata-tag-chip-leave-active {
    --pm-tag-chip-enter-duration: 0ms;
    --pm-tag-chip-leave-duration: 0ms;
  }
}

:global(.pm-tag-inline-menu) {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.1);
  border-radius: 12px;
  background: rgba(var(--v-theme-surface-2), 0.98);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.16);
  padding: 3px;
}

:global(.pm-tag-inline-menu .v-list) {
  overflow: auto;
  background: transparent;
  padding: 0;
}

:global(.pm-tag-inline-menu .v-list-item) {
  min-height: 32px;
  margin: 1px 0;
  border-radius: 10px;
}

:global(.pm-tag-inline-menu .v-list-item-title) {
  font-size: 0.8rem;
}
</style>
