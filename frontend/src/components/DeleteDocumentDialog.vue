<template>
  <DestructiveDialog
    :model-value="modelValue"
    :title="title"
    :header-subtitle="headerSubtitle"
    :max-width="maxWidth"
    :loading="loading"
    :persistent="persistent"
    :primary-text="primaryText"
    :secondary-text="secondaryText"
    :icon="icon"
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
  title: { type: String, default: 'Dokument löschen' },
  documentName: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  persistent: { type: Boolean, default: false },
  maxWidth: { type: [String, Number], default: 480 },
  headerSubtitle: { type: String, default: 'Möchtest du dieses Dokument wirklich löschen?' },
  primaryText: { type: String, default: 'Dokument löschen' },
  secondaryText: { type: String, default: 'Abbrechen' },
  icon: { type: String, default: '' },
  dangerRequireConfirmText: { type: String, default: '' }
});

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel', 'close']);
</script>

<style scoped>
.pm-delete-document__name {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.86);
  font-size: 0.98rem;
  font-weight: 650;
  line-height: 1.45;
}
</style>
