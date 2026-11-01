<template>
  <span class="ocr-details-anchor" @click.stop>
    <v-menu v-model="open" location="bottom start" :offset="10" :close-on-content-click="false" :z-index="6000" max-width="390">
      <template #activator="{ props: activatorProps }">
        <button v-bind="activatorProps" ref="trigger" type="button" class="details-ocr-status ocr-details-trigger" aria-haspopup="dialog"
          :class="`details-ocr-status--${status.tone}`" aria-label="OCR-Details anzeigen" title="Details zur Texterkennung">
          <v-progress-circular v-if="status.tone === 'progress'" indeterminate size="11" width="2" aria-hidden="true" />
          <v-icon v-else size="13" aria-hidden="true">{{ status.icon }}</v-icon>
          {{ status.text }}
        </button>
      </template>
      <section class="ocr-details" role="dialog" :aria-labelledby="titleId" @click.stop @keydown.esc.stop.prevent="close">
        <header class="ocr-details__header">
          <div><div class="ocr-details__title-row"><h3 :id="titleId">{{ showText ? 'Erkannter Text' : 'Texterkennung' }}</h3>
            <button v-if="!showText" type="button" class="ocr-details__info" :class="{ 'ocr-details__info--active': showHelp }"
              aria-label="Was macht OCR?" :aria-expanded="showHelp" :aria-controls="`${titleId}-help`" title="Was macht OCR?" @click="toggleHelp" @keydown.enter.stop @keydown.space.stop><v-icon size="16" aria-hidden="true">mdi-information-outline</v-icon></button>
          </div><p v-if="showText">Zum Lesen und Kopieren</p></div>
          <button type="button" class="ocr-details__close" aria-label="OCR-Details schließen" @click="close"><v-icon size="19" aria-hidden="true">mdi-close</v-icon></button>
          <v-expand-transition :disabled="!helpMotionEnabled">
            <div v-show="showHelp" :id="`${titleId}-help`" class="ocr-details__help" :aria-hidden="!showHelp"><aside class="ocr-details__explanation"><strong>Was macht OCR?</strong><p>OCR macht Scans und Bilder durchsuchbar und liefert Text zum Kopieren und für die KI-Auswertung.</p></aside></div>
          </v-expand-transition>
        </header>
        <template v-if="!showText">
          <div v-if="details.quality" class="ocr-details__quality" :class="`ocr-details__quality--${details.quality}`">
            <div class="ocr-details__quality-heading"><span>Erkennungsqualität</span><strong>{{ details.qualityLabel }}</strong></div>
            <div class="ocr-details__scale"
              :role="details.score === null ? 'img' : 'meter'" :aria-label="`Qualitätsskala der Texterkennung: ${details.qualityLabel}`"
              :aria-valuemin="details.score === null ? undefined : 0" :aria-valuemax="details.score === null ? undefined : 100"
              :aria-valuenow="details.score ?? undefined"
              :aria-valuetext="details.score === null ? undefined : `${details.scoreLabel} Erkennungssicherheit, ${details.qualityLabel}`">
              <span class="ocr-details__range ocr-details__range--poor" /><span class="ocr-details__range ocr-details__range--medium" /><span class="ocr-details__range ocr-details__range--good" />
              <span v-if="details.score !== null" class="ocr-details__marker" :style="{ left: `${Math.max(1, Math.min(99, details.score))}%` }" aria-hidden="true" />
            </div>
            <div class="ocr-details__legend" aria-hidden="true"><span>Schlecht</span><span>Mittel</span><span>Gut</span></div>
            <p v-if="details.score !== null" class="ocr-details__confidence">Erkennungssicherheit <strong>{{ details.scoreLabel }}</strong></p>
            <p v-if="details.message && details.message.trim() !== 'OCR-Qualität gut.'" class="ocr-details__message">{{ details.message }}</p>
          </div>
          <div v-else class="ocr-details__unrated">
            <strong>{{ details.qualityLabel }}</strong>
            <p>{{ details.message }}</p>
            <button v-if="details.needsAssessment" type="button" class="ocr-details__reassess" :disabled="busy" @click="retry">
              <v-icon size="16" aria-hidden="true">mdi-refresh</v-icon>Erneut erkennen und bewerten
            </button>
          </div>
          <dl class="ocr-details__facts">
            <dt>Status</dt><dd>{{ details.status }}</dd>
            <template v-if="details.source"><dt>Textquelle</dt><dd>{{ details.source }}</dd></template>
            <template v-if="details.duration"><dt>Dauer</dt><dd>{{ details.duration }}</dd></template>
            <template v-if="details.finished"><dt>Letzter Durchlauf</dt><dd>{{ details.finished }}</dd></template>
          </dl>
          <footer class="ocr-details__actions">
            <button type="button" :disabled="!details.hasText" @click="showText = true"><v-icon size="16" aria-hidden="true">mdi-text-recognition</v-icon>Erkannten Text ansehen</button>
            <button v-if="!details.needsAssessment" type="button" :disabled="busy" @click="retry"><v-icon size="16" aria-hidden="true">mdi-refresh</v-icon>Erneut erkennen</button>
          </footer>
          <p v-if="!details.hasText" class="ocr-details__no-text">Noch kein erkannter Text verfügbar.</p>
        </template>
        <template v-else>
          <pre class="ocr-details__text" tabindex="0" aria-label="Erkannter Dokumenttext">{{ details.text }}</pre>
          <footer class="ocr-details__actions"><button type="button" @click="showText = false">Zurück zu den OCR-Details</button></footer>
        </template>
      </section>
    </v-menu>
  </span>
</template>

<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue';
import { resolveOcrDetails } from '../utils/ocrDetails.js';
const props = defineProps({ document: { type: Object, required: true }, status: { type: Object, required: true }, busy: Boolean });
const emit = defineEmits(['retry']);
const open = ref(false), showText = ref(false);
const showHelp = ref(false), helpMotionEnabled = ref(true);
const trigger = ref(null);
const titleId = `ocr-details-${useId()}`;
const details = computed(() => resolveOcrDetails(props.document, props.status.tone));
watch(() => props.document.id, () => { open.value = false; showText.value = false; });
watch(open, value => { if (!value) { showText.value = false; showHelp.value = false; } });
watch(showText, value => { if (value) showHelp.value = false; });
function toggleHelp() {
  helpMotionEnabled.value = !trigger.value?.closest('.pm-no-animations') && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  showHelp.value = !showHelp.value;
}
function retry() { if (props.busy) return; open.value = false; emit('retry'); }
function close() { open.value = false; void nextTick(() => trigger.value?.focus({ preventScroll: true })); }
</script>

<style scoped>
.ocr-details-anchor { display:inline-flex; }
.ocr-details-trigger { position:relative; isolation:isolate; appearance:none; font:inherit; font-weight:600; background:transparent; border:0; padding:4px 8px; border-radius:999px; cursor:pointer; }
.ocr-details-trigger::before { content:''; position:absolute; inset:0; z-index:-1; border:1px solid color-mix(in srgb, currentColor 55%, transparent); border-radius:999px; background:color-mix(in srgb, currentColor 8%, transparent); opacity:0; transition:opacity 160ms ease; }
.ocr-details-trigger:hover::before { opacity:1; }
.ocr-details-trigger:focus-visible { outline:2px solid var(--pm-accent); outline-offset:4px; }
.ocr-details-trigger.details-ocr-status--failed { border:1px dashed rgba(var(--v-theme-error), .72); padding:3px 7px; border-radius:999px; background:rgba(var(--v-theme-error), .04); }
.ocr-details-trigger.details-ocr-status--failed::before { content:none; }
.ocr-details-trigger.details-ocr-status--failed:hover { background:rgba(var(--v-theme-error), .1); }
:global(.pm-no-animations .ocr-details-trigger::before) { transition:none; }
@media(prefers-reduced-motion:reduce) { .ocr-details-trigger::before { transition:none; } }
.ocr-details { width:380px; max-width:calc(100vw - 24px); max-height:calc(100dvh - 32px); overflow-y:auto; padding:20px; border:1px solid var(--pm-divider); border-radius:18px; background:var(--pm-app-surface-raised, #fff); color:var(--pm-text); box-shadow:0 14px 48px rgb(0 0 0 / .2); font-size:12px; line-height:1.5; }
.ocr-details__header { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-start; gap:0 12px; margin-bottom:18px; }
.ocr-details__title-row { display:flex; align-items:center; gap:6px; }
.ocr-details__info { display:grid; place-items:center; width:28px; height:28px; border-radius:50%; color:var(--pm-muted); }
.ocr-details__info:hover, .ocr-details__info--active { color:var(--pm-accent); background:color-mix(in srgb, var(--pm-accent) 8%, transparent); }
.ocr-details__info:focus-visible { outline:2px solid var(--pm-accent); outline-offset:2px; }
.ocr-details__header h3 { margin:0; font-size:17px; font-weight:650; letter-spacing:-.02em; }
.ocr-details__header p { margin:2px 0 0; color:var(--pm-muted); }
.ocr-details__close { display:grid; place-items:center; flex:0 0 28px; width:28px; height:28px; border-radius:50%; color:var(--pm-muted); }
.ocr-details__close:hover { background:rgba(var(--v-theme-on-surface), .06); }
.ocr-details__quality { --quality-color:var(--pm-muted); }
.ocr-details__quality--good { --quality-color:rgb(var(--v-theme-success)); }
.ocr-details__quality--warning { --quality-color:rgb(var(--v-theme-warning)); }
.ocr-details__quality--error { --quality-color:rgb(var(--v-theme-error)); }
.ocr-details__quality-heading { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:12px; }
.ocr-details__quality-heading > span { color:var(--pm-muted); }
.ocr-details__quality-heading strong { color:var(--quality-color); }
.ocr-details__scale { position:relative; display:grid; grid-template-columns:3fr 1fr 1fr; gap:3px; height:8px; border-radius:999px; }
.ocr-details__range { border-radius:999px; }
.ocr-details__range--poor { background:#cb5757; }
.ocr-details__range--medium { background:#d6a13a; }
.ocr-details__range--good { background:#4a9b72; }
.ocr-details__marker { position:absolute; top:-4px; width:4px; height:16px; border:1px solid var(--pm-app-surface-raised, #fff); border-radius:3px; background:var(--pm-text); box-shadow:0 0 0 1px var(--pm-text); transform:translateX(-50%); }
.ocr-details__legend { display:grid; grid-template-columns:3fr 1fr 1fr; gap:3px; margin-top:6px; color:var(--pm-muted); font-size:10px; }
.ocr-details__legend span:nth-child(2) { text-align:center; }
.ocr-details__legend span:last-child { text-align:right; }
.ocr-details__confidence { display:flex; justify-content:space-between; gap:8px; margin-top:12px; color:var(--pm-muted); }
.ocr-details__confidence strong { color:var(--pm-text); font-variant-numeric:tabular-nums; }
.ocr-details__message { margin:10px 0 0; color:var(--pm-text); }
.ocr-details__unrated { padding:12px 14px; border:1px solid var(--pm-divider); border-radius:12px; }
.ocr-details__unrated > strong { font-size:13px; font-weight:600; }
.ocr-details__unrated p { margin:4px 0 0; color:var(--pm-muted); }
.ocr-details__reassess { display:inline-flex; align-items:center; gap:6px; margin-top:12px; padding:6px 10px; border:1px solid var(--pm-divider); border-radius:999px; color:var(--pm-accent); font-weight:600; }
.ocr-details__reassess:hover:not(:disabled) { border-color:var(--pm-accent); background:rgba(var(--v-theme-primary), .06); }
.ocr-details__reassess:focus-visible { outline:2px solid var(--pm-accent); outline-offset:3px; }
.ocr-details__reassess:disabled { opacity:.55; cursor:default; }
.ocr-details__facts { display:grid; grid-template-columns:auto minmax(0, 1fr); gap:8px 12px; padding-top:16px; margin:16px 0 0; border-top:1px solid var(--pm-divider); }
.ocr-details__facts dt { color:var(--pm-muted); }
.ocr-details__facts dd { margin:0; text-align:right; overflow-wrap:anywhere; }
.ocr-details__help { display:flow-root; flex-basis:100%; min-width:0; }
.ocr-details__help.expand-transition-enter-active, .ocr-details__help.expand-transition-leave-active { transition:height 200ms ease, opacity 180ms ease !important; }
.ocr-details__help.expand-transition-enter-from, .ocr-details__help.expand-transition-leave-to { opacity:0; }
.ocr-details__explanation { margin-top:12px; padding:12px 14px; border-radius:12px; background:rgba(var(--v-theme-primary), .055); }
.ocr-details__explanation strong { font-weight:600; }
.ocr-details__explanation p { margin:4px 0 0; color:var(--pm-muted); }
.ocr-details__actions { display:flex; flex-wrap:wrap; gap:12px 18px; padding-top:16px; }
.ocr-details__actions button { display:inline-flex; align-items:center; gap:6px; color:var(--pm-accent); font-weight:600; font-size:12px; }
.ocr-details__actions button:hover:not(:disabled) { text-decoration:underline; text-underline-offset:3px; }
.ocr-details__actions button:disabled { color:var(--pm-muted); opacity:.55; cursor:default; }
.ocr-details__actions button:focus-visible, .ocr-details__close:focus-visible, .ocr-details__text:focus-visible { outline:2px solid var(--pm-accent); outline-offset:3px; border-radius:4px; }
.ocr-details__no-text { margin:8px 0 0; font-size:11px; color:var(--pm-muted); }
.ocr-details__text { max-height:min(340px, 48dvh); overflow:auto; padding:12px; border:1px solid var(--pm-divider); border-radius:10px; background:var(--pm-app-surface); font-family:inherit; font-size:12px; line-height:1.65; white-space:pre-wrap; overflow-wrap:anywhere; user-select:text; }
</style>
