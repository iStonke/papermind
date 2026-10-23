<template>
  <div class="import-scan-error" :class="{ 'import-scan-error--compact': compact }" role="alert" aria-atomic="true">
    <button type="button" class="import-scan-error__button" :disabled="disabled || !canRetry"
      :aria-label="canRetry ? 'Erneut scannen' : failure.title" :aria-describedby="messageId" @click="emit('retry')">
      <span class="import-scan-error__icon" aria-hidden="true"><v-icon size="22">mdi-alert-circle-outline</v-icon></span>
      <span class="import-scan-error__copy">
        <strong>{{ failure.title }}</strong>
        <span :id="messageId" class="import-scan-error__message">{{ failure.message }}</span>
        <span v-if="canRetry" class="import-scan-error__retry"><v-icon size="14" aria-hidden="true">mdi-refresh</v-icon>Erneut scannen</span>
      </span>
    </button>
  </div>
</template>

<script setup>
import { useId } from 'vue';
defineProps({
  failure: { type: Object, required: true },
  compact: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  canRetry: { type: Boolean, default: true },
});
const emit = defineEmits(['retry']);
const messageId = `scan-error-${useId()}`;
</script>

<style scoped>
.import-scan-error { min-width: 0; width: 100%; }
.import-scan-error__button {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 68px;
  padding: 11px 13px;
  border: 1px solid rgba(var(--v-theme-error), .3);
  border-radius: 12px;
  background: rgba(var(--v-theme-error), .045);
  color: rgb(var(--v-theme-on-surface));
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.import-scan-error__button:hover:not(:disabled) { background: rgba(var(--v-theme-error), .08); }
.import-scan-error__button:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 3px; }
.import-scan-error__button:disabled { cursor: default; }
.import-scan-error__icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(var(--v-theme-error), .1);
  color: rgb(var(--v-theme-error));
}
.import-scan-error__copy { display: grid; gap: 3px; min-width: 0; }
.import-scan-error__copy strong { font-size: 13.5px; font-weight: 680; line-height: 1.3; }
.import-scan-error__message { font-size: 11px; line-height: 1.45; color: rgba(var(--v-theme-on-surface), .68); }
.import-scan-error__retry { display: inline-flex; align-items: center; gap: 5px; margin-top: 3px; font-size: 11.5px; font-weight: 650; line-height: 1.4; }
.import-scan-error--compact .import-scan-error__button { flex-direction: column; padding: 12px 8px; gap: 8px; text-align: center; }
.import-scan-error--compact .import-scan-error__copy { justify-items: center; }
.import-scan-error--compact .import-scan-error__copy strong { font-size: 12px; }
.import-scan-error--compact .import-scan-error__icon { width: 32px; height: 32px; }
</style>
