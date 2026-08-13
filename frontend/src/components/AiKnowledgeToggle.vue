<template>
  <div class="ai-knowledge-toggle" role="group" aria-label="Wissen: Ansicht wählen">
    <span :class="{ 'ai-knowledge-toggle__label--active': modelValue === 'chat' }">Chat</span>
    <button
      type="button"
      class="ai-knowledge-toggle__switch"
      role="switch"
      :aria-checked="modelValue === 'knowledge'"
      :aria-label="modelValue === 'knowledge' ? 'Zum Chat wechseln' : 'Zur Wissensbasis wechseln'"
      @click="toggleMode"
    >
      <span class="ai-knowledge-toggle__thumb" />
    </button>
    <span :class="{ 'ai-knowledge-toggle__label--active': modelValue === 'knowledge' }">Wissensbasis</span>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    default: 'chat',
    validator: (value) => ['chat', 'knowledge'].includes(value),
  },
});

const emit = defineEmits(['update:modelValue']);

function toggleMode() {
  emit('update:modelValue', props.modelValue === 'knowledge' ? 'chat' : 'knowledge');
}
</script>

<style scoped>
.ai-knowledge-toggle {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: rgb(var(--v-theme-on-surface-variant));
  font-size: 11px;
  font-weight: 650;
  white-space: nowrap;
}

.ai-knowledge-toggle__label--active {
  color: rgb(var(--v-theme-on-surface));
}

.ai-knowledge-toggle__switch {
  position: relative;
  width: 34px;
  height: 19px;
  flex: none;
  padding: 0;
  border: 1px solid rgba(var(--v-theme-on-surface), .14);
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), .1);
  cursor: pointer;
  transition: background-color 140ms ease, border-color 140ms ease;
}

.ai-knowledge-toggle__switch[aria-checked="true"] {
  border-color: rgba(var(--v-theme-primary), .55);
  background: rgb(var(--v-theme-primary));
}

.ai-knowledge-toggle__switch:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}

.ai-knowledge-toggle__thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: rgb(var(--v-theme-surface));
  box-shadow: 0 1px 3px rgba(0, 0, 0, .24);
  transition: transform 140ms ease;
}

.ai-knowledge-toggle__switch[aria-checked="true"] .ai-knowledge-toggle__thumb {
  transform: translateX(15px);
}

@media (prefers-reduced-motion: reduce) {
  .ai-knowledge-toggle__switch,
  .ai-knowledge-toggle__thumb {
    transition: none;
  }
}
</style>
