<template>
  <BaseDialog
    :model-value="modelValue"
    :title="title"
    :description="description"
    variant="confirm"
    :primary-text="primaryText"
    :secondary-text="secondaryText"
    :show-secondary="showSecondary"
    :icon="icon"
    :max-width="maxWidth"
    :persistent="persistent"
    :loading="loading"
    :primary-disabled="primaryDisabled"
    :danger-require-confirm-text="dangerRequireConfirmText"
    @update:model-value="emit('update:modelValue', $event)"
    @primary="emit('primary')"
    @secondary="emit('secondary')"
    @close="emit('close')"
  >
    <slot />
  </BaseDialog>
</template>

<script setup>
import BaseDialog from './BaseDialog.vue';

defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  primaryText: { type: String, default: '' },
  secondaryText: { type: String, default: 'Abbrechen' },
  showSecondary: { type: Boolean, default: true },
  icon: { type: String, default: '' },
  maxWidth: { type: [String, Number], default: 720 },
  persistent: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  primaryDisabled: { type: Boolean, default: false },
  dangerRequireConfirmText: { type: String, default: '' }
});

const emit = defineEmits(['update:modelValue', 'primary', 'secondary', 'close']);
</script>
