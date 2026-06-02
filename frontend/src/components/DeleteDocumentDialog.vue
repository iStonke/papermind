<template>
  <DestructiveDialog
    :model-value="modelValue"
    title="Dokument löschen"
    :header-subtitle="headerSubtitle"
    :max-width="maxWidth"
    :loading="loading"
    :persistent="persistent"
    :primary-text="primaryText"
    :secondary-text="secondaryText"
    :danger-require-confirm-text="dangerRequireConfirmText"
    @update:model-value="emit('update:modelValue', $event)"
    @primary="emit('confirm')"
    @secondary="emit('cancel')"
    @close="emit('close')"
  >
    <p class="pm-delete-document__name">„{{ documentName || 'Unbenanntes Dokument' }}“</p>
  </DestructiveDialog>
</template>

<script setup>
import DestructiveDialog from './DestructiveDialog.vue';

defineProps({
  modelValue: { type: Boolean, default: false },
  documentName: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  persistent: { type: Boolean, default: false },
  maxWidth: { type: [String, Number], default: 460 },
  headerSubtitle: { type: String, default: 'Möchtest du dieses Dokument wirklich löschen?' },
  primaryText: { type: String, default: 'Dokument löschen' },
  secondaryText: { type: String, default: 'Abbrechen' },
  dangerRequireConfirmText: { type: String, default: '' }
});

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel', 'close']);
</script>

<style scoped>
.pm-delete-document__name {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.4;
}
</style>
