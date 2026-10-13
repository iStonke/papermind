<template>
  <div class="vocabulary-search">
    <v-text-field
      ref="field"
      :model-value="modelValue"
      :aria-label="searchLabel"
      placeholder="Name suchen oder neu hinzufügen…"
      prepend-inner-icon="mdi-magnify"
      density="compact"
      variant="solo-filled"
      flat
      hide-details
      clearable
      :readonly="creating"
      @update:model-value="$emit('update:modelValue', $event || '')"
      @keydown.enter="handleEnter"
    >
      <template #append-inner>
        <v-btn
          variant="flat"
          size="small"
          :color="canCreate ? 'primary' : undefined"
          prepend-icon="mdi-plus"
          class="vocabulary-search__create"
          :aria-label="createLabel"
          :disabled="!canCreate || creating"
          :loading="creating"
          @click="$emit('create')"
        >
          Hinzufügen
        </v-btn>
      </template>
    </v-text-field>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  modelValue: { type: String, default: '' },
  searchLabel: { type: String, required: true },
  createLabel: { type: String, required: true },
  canCreate: { type: Boolean, default: false },
  creating: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue', 'create']);
const field = ref(null);

function handleEnter(event) {
  if (event.target?.tagName !== 'INPUT' || event.isComposing) return;
  event.preventDefault();
  if (props.canCreate && !props.creating) emit('create');
}

defineExpose({ focus: () => field.value?.focus() });
</script>

<style scoped>
.vocabulary-search { margin: 18px 0 8px; }
.vocabulary-search :deep(.v-field) { border-radius: 10px; }
.vocabulary-search :deep(.v-field.v-field--variant-solo-filled .v-field__overlay) { opacity: 0.04; }
.vocabulary-search :deep(.v-field--focused) {
  box-shadow: inset 0 0 0 1px rgba(var(--v-theme-primary), 0.45);
}
.vocabulary-search :deep(.v-field__append-inner) { align-items: center; padding-top: 0; }
.vocabulary-search__create {
  flex: 0 0 auto;
  min-width: 0;
  padding-inline: 10px;
  border: 1px solid transparent;
  text-transform: none;
  letter-spacing: 0;
}
.vocabulary-search__create.v-btn--disabled {
  background: rgba(var(--v-theme-on-surface), 0.035);
  border-color: transparent;
  color: rgba(var(--v-theme-on-surface), 0.28);
}
.vocabulary-search__create.v-btn--disabled :deep(.v-btn__overlay) { opacity: 0; }
</style>
