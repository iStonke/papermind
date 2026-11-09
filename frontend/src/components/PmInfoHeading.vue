<!--
  PmInfoHeading — Abschnittsüberschrift mit Popover für die Erklärung aus dem
  Standard-Slot. Rechts stehen optionale Aktionen aus dem Slot `actions`.
-->
<template>
  <div class="pm-info-heading" :class="`pm-info-heading--${variant}`">
    <div class="pm-info-heading__row">
      <component :is="tag" :id="headingId" class="pm-info-heading__title">{{ title }}</component>
      <v-overlay
        v-if="$slots.default"
        ref="popoverRef"
        v-model="open"
        attach=".papermind-app"
        location-strategy="connected"
        location="bottom start"
        scroll-strategy="close"
        :offset="8"
        :scrim="false"
        :transition="{ css: false }"
        :content-props="{
          id: panelId,
          role: 'dialog',
          tabindex: -1,
          'aria-label': label,
          'aria-describedby': noteId,
          onKeydown: onPopoverKeydown,
        }"
        @after-enter="focusPopover"
      >
        <template #activator="{ props: activatorProps }">
          <button
            v-bind="activatorProps"
            type="button"
            class="pm-info-heading__info"
            :class="{ 'is-active': open }"
            :aria-label="label"
            :title="label"
            aria-haspopup="dialog"
            :aria-expanded="open"
            :aria-controls="open ? panelId : undefined"
          ><v-icon size="16" aria-hidden="true">mdi-information-outline</v-icon></button>
        </template>
        <div :id="noteId" class="pm-info-heading__note"><slot /></div>
      </v-overlay>
      <div v-if="$slots.actions" class="pm-info-heading__actions"><slot name="actions" /></div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, useId, watch } from 'vue';

const props = defineProps({
  title: { type: String, required: true },
  /** Überschriftenebene, z. B. 'h2'. */
  tag: { type: String, default: 'h2' },
  /** id der Überschrift (für aria-labelledby des Abschnitts). */
  headingId: { type: String, default: undefined },
  infoLabel: { type: String, default: '' },
  /** 'title' (Abschnittsüberschrift) oder 'label' (kleine Versal-Beschriftung, z. B. im Steckbrief). */
  variant: { type: String, default: 'title' },
  /** Wechselt z. B. mit dem angezeigten Eintrag; schließt die Erklärung wieder. */
  resetKey: { type: [String, Number], default: '' },
});

const open = ref(false);
const popoverRef = ref(null);
const label = computed(() => props.infoLabel || `Was bedeutet ${props.title}?`);
const panelId = `pm-info-${useId()}`;
const noteId = `${panelId}-note`;

function focusPopover() {
  if (open.value) popoverRef.value?.contentEl?.focus({ preventScroll: true });
}

function onPopoverKeydown(event) {
  if (event.key === 'Escape') {
    event.stopPropagation();
    event.preventDefault();
  } else if (event.key !== 'Tab') {
    return;
  }
  open.value = false;
  popoverRef.value?.activatorEl?.focus({ preventScroll: true });
}
watch(() => props.resetKey, () => { open.value = false; });
</script>

<style scoped>
.pm-info-heading { margin-bottom: 10px; }
.pm-info-heading__row { display: flex; align-items: center; gap: 4px; min-height: 28px; }
.pm-info-heading__title { margin: 0; color: var(--pm-text); font-size: 0.95rem; font-weight: 650; }
.pm-info-heading--label { margin-bottom: 6px; }
.pm-info-heading--label .pm-info-heading__row { min-height: 24px; }
.pm-info-heading--label .pm-info-heading__title {
  color: var(--pm-muted);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.pm-info-heading--label .pm-info-heading__info { width: 24px; height: 24px; }
.pm-info-heading__info {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: none;
  color: var(--pm-muted);
  cursor: pointer;
}
.pm-info-heading__info:hover,
.pm-info-heading__info.is-active { color: var(--pm-accent); background: color-mix(in srgb, var(--pm-accent) 8%, transparent); }
.pm-info-heading__info:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 2px; }
.pm-info-heading__actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.pm-info-heading__note {
  width: min(330px, calc(100vw - 24px));
  max-width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--pm-divider);
  border-radius: 12px;
  background: var(--pm-app-surface-raised);
  box-shadow: var(--pm-shadow);
  color: var(--pm-text);
  font-size: 0.84rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.pm-info-heading__note :deep(p) { margin: 0; }
.pm-info-heading__note :deep(p + p) { margin-top: 6px; }
.pm-info-heading__note :deep(strong) { color: var(--pm-text); font-weight: 600; }
</style>
