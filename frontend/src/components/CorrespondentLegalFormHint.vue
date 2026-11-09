<template>
  <!-- Erkannte Rechtsform: Name bleibt offiziell, angezeigt wird kurz – oder bewusst vollständig. -->
  <Transition name="legal-form-hint">
    <p v-if="split.legalForm" class="legal-form-hint" role="status">
      <span class="legal-form-hint__text">
        <template v-if="keep">Angezeigt als „{{ fullName }}“</template>
        <template v-else>Angezeigt als „{{ split.base }}“ (ohne {{ split.legalForm }})</template>
      </span>
      <button type="button" class="legal-form-hint__toggle" :disabled="disabled" @click="emit('update:keep', !keep)">
        {{ keep ? `Ohne ${split.legalForm} anzeigen` : `${split.legalForm} mit anzeigen` }}
      </button>
    </p>
  </Transition>
</template>
<script setup>
import { computed } from 'vue';
import { splitLegalForm } from '../utils/legalForms.js';

const props = defineProps({ name: { type: String, default: '' }, keep: Boolean, disabled: Boolean });
const emit = defineEmits(['update:keep']);
const split = computed(() => splitLegalForm(props.name));
const fullName = computed(() => `${split.value.base} ${split.value.legalForm}`);
</script>
<style scoped>
.legal-form-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px 8px;
  margin: -6px 0 0;
  padding-inline: 4px;
  color: rgb(var(--v-theme-on-surface-variant));
  font-size: 12px;
  line-height: 1.4;
}
.legal-form-hint__text { min-width: 0; }
.legal-form-hint__toggle {
  padding: 0;
  border: 0;
  background: transparent;
  color: rgb(var(--v-theme-primary));
  font: inherit;
  cursor: pointer;
}
.legal-form-hint__toggle:hover:not(:disabled) { text-decoration: underline; }
.legal-form-hint__toggle:disabled { opacity: .5; cursor: default; }
.legal-form-hint__toggle:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 2px; border-radius: 4px; }
.legal-form-hint-enter-active, .legal-form-hint-leave-active { transition: opacity 180ms ease, transform 220ms cubic-bezier(.22, 1, .36, 1); }
.legal-form-hint-enter-from, .legal-form-hint-leave-to { opacity: 0; transform: translateY(-3px); }
:global(.pm-no-animations .legal-form-hint-enter-active),
:global(.pm-no-animations .legal-form-hint-leave-active) { transition: none; }
@media (prefers-reduced-motion: reduce) {
  .legal-form-hint-enter-active, .legal-form-hint-leave-active { transition: none; }
}
@media (pointer: coarse) {
  .legal-form-hint__toggle { min-height: 44px; }
}
</style>
