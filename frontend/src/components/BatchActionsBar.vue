<template>
  <Transition name="batch-bar">
    <div v-if="count > 0" class="batch-bar" role="toolbar" aria-label="Batch-Aktionen">
      <span class="batch-bar__label">{{ count }} {{ count === 1 ? singularLabel : pluralLabel }} ausgewählt</span>

      <div class="batch-bar__actions">
        <v-btn
          v-for="action in resolvedActions"
          :key="action.key"
          variant="tonal"
          :color="action.color"
          size="small"
          class="batch-bar__btn"
          :prepend-icon="action.icon"
          @click="emitAction(action.key)"
        >
          {{ action.label }}
        </v-btn>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  count: { type: Number, default: 0 },
  singularLabel: { type: String, default: 'Dokument' },
  pluralLabel: { type: String, default: 'Dokumente' },
  actions: {
    type: Array,
    default: () => [
      { key: 'tag', label: 'Tags', icon: 'mdi-tag-multiple-outline' },
      { key: 'delete', label: 'In Papierkorb', icon: 'mdi-trash-can-outline', color: 'error' }
    ]
  }
});

const emit = defineEmits(['tag', 'category', 'delete', 'merge', 'action']);

const resolvedActions = computed(() => props.actions.filter((action) => action?.key && action?.label));

function emitAction(key) {
  emit('action', key);
  if (['tag', 'category', 'delete', 'merge'].includes(key)) {
    emit(key);
  }
}
</script>

<style scoped>
.batch-bar {
  position: sticky;
  bottom: 0;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: rgb(var(--v-theme-surface));
  border-top: 1px solid var(--pm-divider);
  box-shadow: 0 -4px 16px rgba(15, 23, 42, 0.08);
}

.batch-bar__label {
  font-size: 0.85rem;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.72);
  white-space: nowrap;
}

.batch-bar__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.batch-bar__btn {
  text-transform: none;
  letter-spacing: 0;
  font-weight: 500;
}

/* Einblend-Animation */
.batch-bar-enter-active,
.batch-bar-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.batch-bar-enter-from,
.batch-bar-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
