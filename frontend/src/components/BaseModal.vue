<template>
  <BaseDialog
    :model-value="modelValue"
    :title="title"
    :description="subtitle"
    :max-width="maxWidth"
    :width="width"
    :persistent="persistent"
    :scrollable="scrollable"
    :loading="closeDisabled"
    :card-class="cardClass"
    :body-class="bodyClass"
    :footer-class="footerClass"
    :primary-text="closeLabel"
    :show-secondary="false"
    variant="info"
    @update:model-value="emit('update:modelValue', $event)"
    @primary="onCloseClick"
    @close="emit('close')"
  >
    <slot />
    <template #footer>
      <slot name="footer">
        <v-btn variant="text" :disabled="closeDisabled" @click="onCloseClick">{{ closeLabel }}</v-btn>
      </slot>
    </template>
  </BaseDialog>
</template>

<script setup>
import BaseDialog from './BaseDialog.vue';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  closeLabel: { type: String, default: 'Schließen' },
  closeDisabled: { type: Boolean, default: false },
  maxWidth: { type: [String, Number], default: 520 },
  width: { type: [String, Number], default: undefined },
  persistent: { type: Boolean, default: false },
  scrollable: { type: Boolean, default: false },
  cardClass: { type: [String, Array, Object], default: '' },
  bodyClass: { type: [String, Array, Object], default: '' },
  footerClass: { type: [String, Array, Object], default: '' }
});

const emit = defineEmits(['update:modelValue', 'close']);

function onCloseClick() {
  if (props.closeDisabled) {
    return;
  }
  emit('update:modelValue', false);
  emit('close');
}
</script>
