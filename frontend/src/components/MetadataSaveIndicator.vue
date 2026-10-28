<template>
  <span class="metadata-save" role="status" aria-live="polite" aria-atomic="true">
    <Transition name="metadata-save">
      <span v-if="saving || saved" :key="saving ? 'saving' : 'saved'" class="metadata-save__message">
        <svg v-if="saved && !saving" viewBox="0 0 16 16" aria-hidden="true"><path d="m3 8 3.2 3.2L13 4.5" /></svg>
        {{ saving ? 'Wird gespeichert …' : 'Gespeichert' }}
      </span>
    </Transition>
  </span>
</template>
<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';
const props = defineProps({ saving: Boolean, error: Boolean, documentKey: [String, Number] });
const saved = ref(false);
let timer;
let saveDocumentKey;
watch(() => props.saving, (saving, wasSaving) => {
  window.clearTimeout(timer);
  saved.value = false;
  if (saving) saveDocumentKey = props.documentKey;
  else if (wasSaving && !props.error && saveDocumentKey === props.documentKey) {
    saved.value = true;
    timer = window.setTimeout(() => { saved.value = false; }, 2200);
  }
});
watch(() => props.documentKey, () => { saved.value = false; window.clearTimeout(timer); });
watch(() => props.error, error => { if (error) saved.value = false; });
onBeforeUnmount(() => window.clearTimeout(timer));
</script>
<style scoped>
.metadata-save { position: relative; display: inline-grid; min-height: 16px; color: var(--pm-accent); font-size: 11px; font-weight: 500; letter-spacing: 0; text-transform: none; }
.metadata-save__message { grid-area: 1 / 1; display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.metadata-save svg { width: 14px; height: 14px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.metadata-save-enter-active, .metadata-save-leave-active { transition: opacity 160ms ease, transform 180ms ease; }
.metadata-save-enter-from { opacity: 0; transform: translateY(3px); }
.metadata-save-leave-to { opacity: 0; transform: translateY(-3px); }
:global(.pm-no-animations) .metadata-save__message { transition: none; transform: none; }
@media (prefers-reduced-motion: reduce) { .metadata-save__message { transition: none; transform: none; } }
</style>
