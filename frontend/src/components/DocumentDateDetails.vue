<template>
  <span class="document-date-anchor" @click.stop>
    <v-menu v-model="open" location="bottom start" :offset="10" :close-on-content-click="false" :z-index="6000" max-width="390">
      <template #activator="{ props: activatorProps }">
        <button v-bind="activatorProps" ref="trigger" type="button" class="document-date-trigger" aria-haspopup="dialog"
          aria-label="Datumsangaben anzeigen" title="Datumsangaben zum Dokument"><v-icon size="13" aria-hidden="true">mdi-calendar-clock</v-icon>{{ createdLabel === '-' ? 'Datumsangaben' : createdLabel }}</button>
      </template>
      <section class="document-dates" role="dialog" :aria-labelledby="titleId" @click.stop @keydown.esc.stop.prevent="close">
        <header class="document-dates__header">
          <div class="document-dates__title-row"><h3 :id="titleId">Datumsangaben</h3>
            <button type="button" class="document-dates__info" :class="{ 'document-dates__info--active': showHelp }"
              aria-label="Datumsangaben erklären" :aria-expanded="showHelp" :aria-controls="`${titleId}-help`" title="Was bedeutet das Datum?"
              @click="toggleHelp" @keydown.enter.stop @keydown.space.stop><v-icon size="16" aria-hidden="true">mdi-information-outline</v-icon></button>
          </div>
          <button type="button" class="document-dates__close" aria-label="Datumsangaben schließen" @click="close"><v-icon size="19" aria-hidden="true">mdi-close</v-icon></button>
          <v-expand-transition :disabled="!helpMotionEnabled">
            <div v-show="showHelp" :id="`${titleId}-help`" class="document-dates__help" :aria-hidden="!showHelp">
              <aside class="document-dates__explanation"><strong>Was bedeutet das Datum?</strong><p>Das Datum in der Kopfzeile zeigt, wann dieses Dokument zu PaperMind hinzugefügt wurde.</p></aside>
            </div>
          </v-expand-transition>
        </header>
        <dl class="document-dates__facts">
          <template v-for="field in fields" :key="field.label"><dt>{{ field.label }}</dt><dd>
            <time v-if="field.datetime" :datetime="field.datetime">{{ field.value }}</time><span v-else class="document-dates__missing">{{ field.value }}</span>
          </dd></template>
        </dl>
      </section>
    </v-menu>
  </span>
</template>

<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue';
import { formatDateTime, formatDocumentDateInputFromIso } from '../utils/dates.js';

const props = defineProps({ document: { type: Object, required: true } });
const open = ref(false), showHelp = ref(false), helpMotionEnabled = ref(true), trigger = ref(null);
const titleId = `document-dates-${useId()}`;
const createdLabel = computed(() => formatDateTime(props.document.created_at));
const fields = computed(() => [
  { label: 'Hinzugefügt am', raw: props.document.created_at, formatted: createdLabel.value, empty: 'Nicht verfügbar' },
  { label: 'Dokumentdatum', raw: props.document.document_date, formatted: formatDocumentDateInputFromIso(props.document.document_date), empty: 'Nicht angegeben' },
  { label: 'Zuletzt geändert', raw: props.document.updated_at, formatted: formatDateTime(props.document.updated_at), empty: 'Nicht verfügbar' }
].map(field => {
  const present = field.formatted && field.formatted !== '-';
  return { label: field.label, value: present ? field.formatted : field.empty, datetime: present ? field.raw : null };
}));
watch(() => props.document.id, () => { open.value = false; showHelp.value = false; });
watch(open, value => { if (!value) showHelp.value = false; });
function toggleHelp() {
  helpMotionEnabled.value = !trigger.value?.closest('.pm-no-animations') && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  showHelp.value = !showHelp.value;
}
function close() { open.value = false; void nextTick(() => trigger.value?.focus({ preventScroll: true })); }
</script>

<style scoped>
.document-date-anchor { display:inline-flex; }
.document-date-trigger { position:relative; isolation:isolate; display:inline-flex; align-items:center; gap:5px; appearance:none; font:inherit; color:inherit; background:transparent; border:0; padding:4px 8px; border-radius:999px; white-space:nowrap; cursor:pointer; }
.document-date-trigger::before { content:''; position:absolute; inset:0; z-index:-1; border:1px solid color-mix(in srgb, currentColor 55%, transparent); border-radius:999px; background:color-mix(in srgb, currentColor 8%, transparent); opacity:0; transition:opacity 160ms ease; }
.document-date-trigger:hover::before { opacity:1; }
.document-date-trigger:focus-visible { outline:2px solid var(--pm-accent); outline-offset:4px; }
:global(.pm-no-animations .document-date-trigger::before) { transition:none; }
@media(prefers-reduced-motion:reduce) { .document-date-trigger::before { transition:none; } }
.document-dates { width:380px; max-width:calc(100vw - 24px); max-height:calc(100dvh - 32px); overflow-y:auto; padding:20px; border:1px solid var(--pm-divider); border-radius:18px; background:var(--pm-app-surface-raised, #fff); color:var(--pm-text); box-shadow:0 14px 48px rgb(0 0 0 / .2); font-size:12px; line-height:1.5; }
.document-dates__header { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-start; gap:0 12px; margin-bottom:18px; }
.document-dates__title-row { display:flex; align-items:center; gap:6px; }
.document-dates__header h3 { margin:0; font-size:17px; font-weight:650; letter-spacing:-.02em; }
.document-dates__info, .document-dates__close { display:grid; place-items:center; flex:0 0 28px; width:28px; height:28px; border-radius:50%; color:var(--pm-muted); }
.document-dates__info:hover, .document-dates__info--active { color:var(--pm-accent); background:color-mix(in srgb, var(--pm-accent) 8%, transparent); }
.document-dates__close:hover { background:rgba(var(--v-theme-on-surface), .06); }
.document-dates__info:focus-visible, .document-dates__close:focus-visible { outline:2px solid var(--pm-accent); outline-offset:2px; }
.document-dates__help { display:flow-root; flex-basis:100%; min-width:0; }
.document-dates__help.expand-transition-enter-active, .document-dates__help.expand-transition-leave-active { transition:height 200ms ease, opacity 180ms ease !important; }
.document-dates__help.expand-transition-enter-from, .document-dates__help.expand-transition-leave-to { opacity:0; }
.document-dates__explanation { margin-top:12px; padding:12px 14px; border-radius:12px; background:color-mix(in srgb, var(--pm-muted) 6%, transparent); }
.document-dates__explanation strong { font-weight:600; }
.document-dates__explanation p { margin:4px 0 0; color:var(--pm-muted); }
.document-dates__facts { display:grid; grid-template-columns:auto minmax(0, 1fr); gap:12px 16px; }
.document-dates__facts dt { color:var(--pm-muted); }
.document-dates__facts dd { margin:0; text-align:right; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
.document-dates__missing { color:var(--pm-muted); }
</style>
