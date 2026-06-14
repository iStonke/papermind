<template>
  <div class="list-action-toolbar">
    <div class="list-action-toolbar__left">
      <template v-if="selectionMode">
        <button type="button" class="list-action-toolbar__action-btn" @click="emit('select-all')">
          Alle auswählen
        </button>
        <span v-if="selectionCount > 0" class="list-action-toolbar__count">
          {{ selectionCount }} ausgewählt
        </span>
      </template>
      <template v-else>
        <v-menu
          v-for="action in actions"
          :key="action.key"
          location="bottom start"
          offset="4"
          content-class="list-action-toolbar-menu"
        >
          <template #activator="{ props: menuProps }">
            <button
              type="button"
              class="list-action-toolbar__action-btn list-action-toolbar__action-btn--icon"
              :class="{ 'list-action-toolbar__action-btn--active': action.active }"
              v-bind="menuProps"
            >
              <v-icon v-if="action.icon" size="14">{{ action.icon }}</v-icon>
              {{ action.label }}
            </button>
          </template>
          <v-list density="compact" :min-width="action.minWidth || 170" class="list-action-toolbar-menu__list">
            <v-list-item
              v-for="option in action.options || []"
              :key="option.value"
              :class="{ 'v-list-item--active': option.value === action.value }"
              @click="emit('action-select', { action: action.key, value: option.value })"
            >
              <v-list-item-title>{{ option.label }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </template>
    </div>

    <div class="list-action-toolbar__right">
      <button
        v-for="action in rightActions"
        :key="action.key"
        type="button"
        class="list-action-toolbar__select-btn"
        :disabled="action.disabled"
        @click="emit('right-action', action.key)"
      >
        <v-icon v-if="action.icon" size="14">{{ action.icon }}</v-icon>
        {{ action.label }}
      </button>

      <button
        type="button"
        class="list-action-toolbar__select-btn"
        :class="{ 'list-action-toolbar__select-btn--cancel': selectionMode }"
        :disabled="!selectionMode && selectionDisabled"
        @click="emit('toggle-selection')"
      >
        {{ selectionMode ? 'Abbrechen' : 'Auswählen' }}
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  actions: { type: Array, default: () => [] },
  rightActions: { type: Array, default: () => [] },
  selectionMode: { type: Boolean, default: false },
  selectionCount: { type: Number, default: 0 },
  selectionDisabled: { type: Boolean, default: false }
});

const emit = defineEmits(['action-select', 'right-action', 'toggle-selection', 'select-all']);
</script>

<style scoped>
.list-action-toolbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 36px;
  padding: 5px 12px;
  background: rgba(var(--v-theme-surface), 0.84);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--pm-divider);
}

.list-action-toolbar__left {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.list-action-toolbar__right {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.list-action-toolbar__action-btn,
.list-action-toolbar__select-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: none;
  border-radius: 6px;
  padding: 3px 7px;
  background: none;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.01em;
  white-space: nowrap;
  transition: background 0.12s ease, color 0.12s ease;
}

.list-action-toolbar__action-btn {
  color: rgba(var(--v-theme-on-surface), 0.62);
}

.list-action-toolbar__action-btn:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.85);
}

.list-action-toolbar__action-btn:disabled {
  color: rgba(var(--v-theme-on-surface), 0.32);
  cursor: not-allowed;
}

.list-action-toolbar__action-btn:disabled:hover {
  background: transparent;
}

.list-action-toolbar__action-btn--active {
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.list-action-toolbar__select-btn {
  flex-shrink: 0;
  color: rgba(var(--v-theme-on-surface), 0.66);
}

.list-action-toolbar__select-btn:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.86);
}

.list-action-toolbar__select-btn:disabled {
  color: rgba(var(--v-theme-on-surface), 0.32);
  cursor: not-allowed;
}

.list-action-toolbar__select-btn:disabled:hover {
  background: transparent;
}

.list-action-toolbar__select-btn--cancel {
  color: rgba(var(--v-theme-on-surface), 0.55);
}

.list-action-toolbar__select-btn--cancel:hover {
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.list-action-toolbar__count {
  padding-left: 4px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  font-size: 0.78rem;
}

:global(.list-action-toolbar-menu) {
  border-radius: 8px;
}

:global(.list-action-toolbar-menu__list) {
  padding: 4px;
}

:global(.list-action-toolbar-menu__list .v-list-item) {
  min-height: 34px;
  padding-inline: 10px !important;
  border-radius: 6px;
}

:global(.list-action-toolbar-menu__list .v-list-item-title) {
  font-size: 0.88rem;
  line-height: 1.25;
}
</style>
