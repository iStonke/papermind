<template>
  <BaseDialog
    :model-value="modelValue"
    max-width="440"
    title="Tags hinzufügen"
    :header-subtitle="`Wird auf ${count} ${count === 1 ? 'Dokument' : 'Dokumente'} angewendet.`"
    variant="confirm"
    primary-text="Anwenden"
    secondary-text="Abbrechen"
    :loading="loading || isCreating"
    :primary-disabled="selectedItems.length === 0"
    @primary="onConfirm"
    @update:model-value="emit('update:modelValue', $event)"
    @close="onClose"
  >
    <v-combobox
      v-model="selectedItems"
      :items="tags"
      item-title="name"
      item-value="id"
      return-object
      label="Tags auswählen oder neu erstellen"
      density="comfortable"
      variant="outlined"
      multiple
      chips
      closable-chips
      hide-details
      :menu-props="{ maxHeight: 260 }"
      class="batch-tag-autocomplete"
    >
      <template #no-data>
        <div class="batch-tag-no-data">
          <span>Enter drücken, um Tag zu erstellen</span>
        </div>
      </template>
    </v-combobox>
    <p v-if="selectedItems.length > 0" class="batch-tag-hint">
      Bestehende Tags der Dokumente bleiben erhalten.
      <template v-if="newTagNames.length > 0">
        <br>Neu erstellt: {{ newTagNames.join(', ') }}
      </template>
    </p>
  </BaseDialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useTagStore } from '../stores/tags.js';
import BaseDialog from './BaseDialog.vue';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  tags:       { type: Array,   default: () => [] },
  count:      { type: Number,  default: 0 },
  loading:    { type: Boolean, default: false },
});

const emit = defineEmits(['update:modelValue', 'confirm']);

const tagStore    = useTagStore();
const selectedItems = ref([]);
const isCreating    = ref(false);

// Zeigt an welche Einträge neue (noch nicht existierende) Tags sind
const newTagNames = computed(() =>
  selectedItems.value
    .filter((item) => typeof item === 'string' && item.trim())
    .map((item) => item.trim())
);

watch(() => props.modelValue, (open) => {
  if (!open) selectedItems.value = [];
});

async function onConfirm() {
  if (selectedItems.value.length === 0) return;
  isCreating.value = true;

  const tagIds = [];
  try {
    for (const item of selectedItems.value) {
      if (typeof item === 'string') {
        // Neuer Tag — anlegen oder existierenden finden
        const id = await tagStore.ensureTagIdByName(item.trim());
        if (id) tagIds.push(id);
      } else if (item?.id) {
        tagIds.push(item.id);
      }
    }
    emit('confirm', tagIds);
  } finally {
    isCreating.value = false;
  }
}

function onClose() {
  selectedItems.value = [];
  emit('update:modelValue', false);
}
</script>

<style scoped>
.batch-tag-autocomplete {
  margin-top: 4px;
}

.batch-tag-no-data {
  padding: 8px 16px;
  font-size: 0.82rem;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.batch-tag-hint {
  margin: 10px 0 0;
  font-size: 0.8rem;
  color: rgba(var(--v-theme-on-surface), 0.5);
  line-height: 1.5;
}
</style>
