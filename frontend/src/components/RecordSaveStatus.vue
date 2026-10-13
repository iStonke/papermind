<template>
  <div v-if="state === 'error' || state === 'invalid'" class="record-save-status">
    <span role="status" aria-live="polite" aria-atomic="true">
      <v-icon size="16" aria-hidden="true">mdi-alert-circle-outline</v-icon>
      {{ labels[state] }}
    </span>
    <button v-if="state === 'error'" type="button" @click="$emit('retry')">Erneut speichern</button>
  </div>
</template>

<script setup>
defineProps({ state: { type: String, default: 'idle' } });
defineEmits(['retry']);
const labels = {
  error: 'Nicht gespeichert. Dein Entwurf bleibt erhalten.', invalid: 'Bitte einen gültigen Namen eingeben.',
};
</script>

<style scoped>
.record-save-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 0.75rem;
  color: rgb(var(--v-theme-error));
}
.record-save-status > span { display: inline-flex; align-items: center; gap: 7px; }
.record-save-status button {
  border-radius: 6px;
  padding: 5px 8px;
  font-weight: 650;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}
.record-save-status button:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 3px; }
</style>
