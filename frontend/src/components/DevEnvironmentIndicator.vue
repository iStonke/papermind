<template>
  <div v-if="preferences.showEnvironmentIndicator" class="dev-environment" aria-label="DEV-System · Entwicklungsumgebung">
    <span class="dev-environment__label"><strong>DEV</strong> · Entwicklungsumgebung</span>
  </div>
</template>

<script setup>
import { onBeforeUnmount, watch } from 'vue';
import { useDevSettings } from '../composables/useDevSettings.js';

const { preferences } = useDevSettings();
const originalTitle = document.title.replace(/^\[DEV\]\s*/, '');
watch(() => preferences.value.showEnvironmentIndicator, enabled => {
  document.title = enabled ? `[DEV] ${originalTitle}` : originalTitle;
}, { immediate: true });
onBeforeUnmount(() => { document.title = originalTitle; });
</script>

<style scoped>
.dev-environment {
  position: fixed;
  inset: 0;
  z-index: 10000;
  border: 3px solid #fbbf24;
  pointer-events: none;
}
.dev-environment__label {
  position: absolute;
  top: -3px;
  left: 50%;
  transform: translateX(-50%);
  padding: 3px 14px 5px;
  border-radius: 0 0 8px 8px;
  background: #fbbf24;
  color: #422006;
  font: 600 11px/1.3 system-ui, sans-serif;
  white-space: nowrap;
}
.dev-environment__label strong { font-weight: 850; letter-spacing: 0.06em; }
@media print { .dev-environment { display: none; } }
</style>
