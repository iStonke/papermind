<template>
  <span class="document-knowledge-anchor" @click.stop>
    <v-menu v-model="open" location="bottom start" :offset="10" :close-on-content-click="false" :z-index="6000" max-width="390">
      <template #activator="{ props: activatorProps }">
        <button v-bind="activatorProps" ref="trigger" type="button" class="document-knowledge-trigger" aria-haspopup="dialog"
          aria-label="Wissen zum Dokument anzeigen" :aria-describedby="details.missing.length ? `${titleId}-missing` : undefined" title="Ergebnisse der KI-Auswertung">
          <v-progress-circular v-if="busy" indeterminate size="11" width="2" aria-hidden="true" />
          <v-icon v-else size="13" aria-hidden="true">mdi-brain</v-icon>Wissen
          <span v-if="details.missing.length" :id="`${titleId}-missing`" class="document-knowledge-trigger__count">· {{ details.missing.length }} offen</span>
        </button>
      </template>
      <section class="document-knowledge" :class="{ 'document-knowledge--no-motion': !motionEnabled }" role="dialog" :aria-labelledby="titleId" @click.stop @keydown.esc.stop.prevent="close">
        <header class="document-knowledge__header">
          <div><div class="document-knowledge__title-row"><h3 :id="titleId">Wissen</h3>
            <button type="button" class="document-knowledge__info" :class="{ 'document-knowledge__info--active': showHelp }"
              aria-label="Was zeigt Wissen?" :aria-expanded="showHelp" :aria-controls="`${titleId}-help`" title="Was zeigt Wissen?" @click="toggleHelp" @keydown.enter.stop @keydown.space.stop><v-icon size="16" aria-hidden="true">mdi-information-outline</v-icon></button>
          </div><p>Ergebnisse der KI-Auswertung</p></div>
          <button type="button" class="document-knowledge__close" aria-label="Wissen schließen" @click="close"><v-icon size="19" aria-hidden="true">mdi-close</v-icon></button>
          <v-expand-transition :disabled="!helpMotionEnabled">
            <div v-show="showHelp" :id="`${titleId}-help`" class="document-knowledge__help" :aria-hidden="!showHelp"><aside class="document-knowledge__explanation"><strong>Was zeigt Wissen?</strong><p>Wissen zeigt die KI-Kurzfassung und erkannte Angaben. Die Skala zeigt, welche Dokumentfelder bereits ausgefüllt sind.</p></aside></div>
          </v-expand-transition>
        </header>
        <p v-if="details.message" class="document-knowledge__state" :class="`document-knowledge__state--${details.state}`" role="status">{{ details.message }}</p>
        <section v-if="details.summary" class="document-knowledge__section document-knowledge__summary-card">
          <h4>Kurzfassung</h4><p class="document-knowledge__summary" tabindex="0" aria-label="Kurzfassung der KI-Auswertung">{{ details.summary }}</p>
        </section>
        <section class="document-knowledge__section document-knowledge__completeness">
          <div class="document-knowledge__completeness-heading"><h4>Dokumentangaben</h4><span>{{ details.filledCount }} von {{ details.completeness.length }} vorhanden</span></div>
          <div ref="completenessMeter" class="document-knowledge__segments" role="meter" tabindex="-1" aria-label="Vollständigkeit der Dokumentangaben"
            :aria-valuemin="0" :aria-valuemax="details.completeness.length" :aria-valuenow="details.filledCount"
            :aria-valuetext="`${details.filledCount} von ${details.completeness.length} Angaben vorhanden`">
            <span v-for="field in details.completeness" :key="field.label" class="document-knowledge__segment"
              :class="{ 'document-knowledge__segment--filled': field.filled }" :title="`${field.label}: ${field.filled ? 'vorhanden' : 'fehlt'}`" aria-hidden="true" />
          </div>
          <div v-if="!editing && (details.missing.length || busy)" class="document-knowledge__missing">
            <h4 v-if="details.missing.length">Offene Angaben</h4>
            <button ref="completionButton" type="button" class="document-knowledge__complete" :disabled="busy || completionDisabled" :aria-busy="busy"
              :aria-label="completionLabel" :title="`Ergänzt ausschließlich leere Felder mit KI. Offen: ${details.missing.join(', ')}`" @click="complete">
              <v-progress-circular v-if="busy" indeterminate size="12" width="2" aria-hidden="true" />
              <v-icon v-else size="16" aria-hidden="true">mdi-creation</v-icon>{{ completionLabel }}
            </button>
          </div>
          <p v-if="completionError" class="document-knowledge__completion-error" role="alert">{{ completionError }}</p>
        </section>
        <section class="document-knowledge__section">
          <div class="document-knowledge__section-heading"><h4>Erkannte Angaben</h4>
            <button v-if="saveChanges && !editing" ref="editButton" type="button" class="document-knowledge__edit" aria-label="Angaben bearbeiten"
              :disabled="busy || completionDisabled || editingDisabled" title="Angaben korrigieren" @click="startEditing"><v-icon size="16" aria-hidden="true">mdi-pencil-outline</v-icon></button>
          </div>
          <form v-if="editing" class="document-knowledge__editor" aria-label="Angaben korrigieren" @submit.prevent="save" @keydown.esc.stop.prevent="cancelEditing">
            <fieldset :disabled="saving">
              <label :for="`${titleId}-type`">Dokumenttyp</label>
              <input :id="`${titleId}-type`" ref="firstEditorField" v-model="draft.document_type" :list="`${titleId}-types`" maxlength="30" autocomplete="off" />
              <datalist :id="`${titleId}-types`"><option v-for="type in documentTypes" :key="type" :value="type" /></datalist>
              <label :for="`${titleId}-date`">Dokumentdatum</label><input :id="`${titleId}-date`" v-model="draft.document_date" type="date" max="9999-12-31" />
              <label :for="`${titleId}-sender`">Korrespondent</label>
              <select :id="`${titleId}-sender`" v-model="draft.correspondent_id"><option value="">Keine Zuordnung</option><option v-for="item in correspondents" :key="item.value" :value="item.value">{{ item.title }}</option></select>
              <label :for="`${titleId}-recipient`">Empfänger</label><input :id="`${titleId}-recipient`" v-model="draft.recipient" maxlength="255" autocomplete="off" />
              <div class="document-knowledge__money-editor">
                <div><label :for="`${titleId}-amount`">Betrag</label><input :id="`${titleId}-amount`" v-model="draft.amount" inputmode="decimal" placeholder="0,00" autocomplete="off" /></div>
                <div><label :for="`${titleId}-currency`">Währung</label><input :id="`${titleId}-currency`" v-model="draft.currency" maxlength="3" placeholder="EUR" autocomplete="off" /></div>
              </div>
            </fieldset>
            <p class="document-knowledge__edit-hint">Korrekturen bleiben bei einer neuen KI-Auswertung erhalten.</p>
            <p v-if="saveError" class="document-knowledge__completion-error" role="alert">{{ saveError }}</p>
            <div class="document-knowledge__editor-actions"><button type="button" :disabled="saving" @click="cancelEditing">Abbrechen</button>
              <button type="submit" class="document-knowledge__complete" :disabled="saving" :aria-busy="saving">{{ saving ? 'Wird gespeichert …' : 'Speichern' }}</button></div>
          </form>
          <template v-else>
          <p v-if="details.compactPrimary" class="document-knowledge__compact-primary">{{ details.compactPrimary }}</p>
          <p v-if="details.compactParties" class="document-knowledge__compact-parties" :title="details.compactParties">{{ details.compactParties }}</p>
          <p v-if="!details.fields.length" class="document-knowledge__edit-hint">Noch keine Angaben vorhanden.</p>
          <button v-if="details.fields.length" type="button" class="document-knowledge__disclosure" :aria-expanded="expanded" :aria-controls="`${titleId}-fields`" @click="expanded = !expanded">{{ expanded ? 'Weniger anzeigen' : 'Alle Angaben' }}<v-icon size="14" aria-hidden="true">{{ expanded ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon></button>
          <dl v-if="expanded" :id="`${titleId}-fields`" class="document-knowledge__fields"><template v-for="field in details.fields" :key="field.label"><dt>{{ field.label }}</dt>
            <dd :class="{ 'document-knowledge__amount': field.amount !== undefined }"><template v-if="field.amount !== undefined"><strong>{{ field.amount }}</strong><small v-if="field.currency">{{ field.currency }}</small></template><template v-else>{{ field.value }}</template></dd>
          </template></dl>
          <p v-if="saved" class="document-knowledge__saved" role="status">Angaben gespeichert.</p>
          </template>
        </section>
        <section v-if="details.tags.length" class="document-knowledge__section">
          <h4>Vorgeschlagene Tags</h4><div class="document-knowledge__tags"><span v-for="tag in details.tags" :key="tag">{{ tag }}</span></div>
        </section>
        <dl class="document-knowledge__facts">
          <dt>Status</dt><dd><span class="document-knowledge__status" :class="`document-knowledge__status--${details.state}`">{{ details.status }}</span></dd>
          <template v-if="details.processed"><dt>{{ details.processedLabel }}</dt><dd>{{ details.processed }}</dd></template>
        </dl>
      </section>
    </v-menu>
  </span>
</template>

<script setup>
import { computed, nextTick, ref, useId, watch } from 'vue';
import { knowledgeDraft, knowledgePatch, resolveDocumentKnowledge } from '../utils/documentKnowledge.js';
const props = defineProps({ document: { type: Object, required: true }, busy: Boolean, missingFields: Array, completionDisabled: Boolean, completionError: String,
  saveChanges: Function, documentTypes: { type: Array, default: () => [] }, correspondents: { type: Array, default: () => [] }, editingDisabled: Boolean });
const emit = defineEmits(['complete']);
const open = ref(false), trigger = ref(null);
const completionButton = ref(null), completenessMeter = ref(null), completionRequested = ref(false);
const motionEnabled = ref(true);
const showHelp = ref(false), helpMotionEnabled = ref(true);
const expanded = ref(false), editing = ref(false), saving = ref(false), saved = ref(false), saveError = ref('');
const draft = ref({}), editButton = ref(null), firstEditorField = ref(null);
let initialDraft = {}, editSession = 0;
const titleId = `document-knowledge-${useId()}`;
const details = computed(() => resolveDocumentKnowledge(props.document, { busy: props.busy, missingFields: props.missingFields }));
const completionLabel = computed(() => props.busy ? 'Angaben werden ergänzt …'
  : details.value.missing.length === 1 ? `${details.value.missing[0]} mit KI ergänzen` : `${details.value.missing.length} Angaben mit KI ergänzen`);
watch(() => props.document.id, () => { open.value = false; completionRequested.value = false; });
watch(open, value => {
  if (value) motionEnabled.value = !trigger.value?.closest('.pm-no-animations');
  else { completionRequested.value = false; editing.value = false; expanded.value = false; showHelp.value = false; saved.value = false; saveError.value = ''; saving.value = false; editSession++; }
});
function toggleHelp() {
  helpMotionEnabled.value = motionEnabled.value && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  showHelp.value = !showHelp.value;
}
watch(() => props.busy, async (busy, wasBusy) => {
  if (busy || !wasBusy || !completionRequested.value) return;
  completionRequested.value = false;
  const restoreFocus = document.activeElement === document.body || document.activeElement === completionButton.value;
  if (open.value && restoreFocus) {
    await nextTick();
    (details.value.missing.length ? completionButton.value : completenessMeter.value)?.focus({ preventScroll: true });
  }
});
function close() { open.value = false; void nextTick(() => trigger.value?.focus({ preventScroll: true })); }
function complete() {
  if (!props.busy && !props.completionDisabled && !editing.value && details.value.missing.length) {
    completionRequested.value = true;
    emit('complete', props.document.id);
  }
}
async function startEditing() {
  if (props.busy || props.completionDisabled || props.editingDisabled) return;
  editSession++;
  initialDraft = knowledgeDraft(props.document);
  draft.value = { ...initialDraft };
  saveError.value = ''; saved.value = false; editing.value = true;
  await nextTick(); firstEditorField.value?.focus({ preventScroll: true });
}
async function cancelEditing() {
  if (saving.value) return;
  editing.value = false; saveError.value = ''; editSession++;
  await nextTick(); editButton.value?.focus({ preventScroll: true });
}
async function save() {
  if (saving.value || !editing.value) return;
  const session = editSession;
  saveError.value = '';
  try {
    const patch = knowledgePatch(draft.value, initialDraft);
    if (!Object.keys(patch).length) { await cancelEditing(); return; }
    saving.value = true;
    await props.saveChanges(props.document.id, patch);
    if (session !== editSession) return;
    editing.value = false; saved.value = true;
    await nextTick(); editButton.value?.focus({ preventScroll: true });
  } catch (error) {
    if (session === editSession) saveError.value = error?.message || 'Angaben konnten nicht gespeichert werden. Bitte versuche es erneut.';
  } finally { if (session === editSession) saving.value = false; }
}
</script>

<style scoped>
.document-knowledge-anchor { display:inline-flex; }
.document-knowledge-trigger { position:relative; isolation:isolate; display:inline-flex; align-items:center; gap:5px; flex:0 0 auto; appearance:none; font:inherit; color:var(--pm-muted); background:transparent; border:0; padding:4px 8px; border-radius:999px; white-space:nowrap; cursor:pointer; }
.document-knowledge-trigger::before { content:''; position:absolute; inset:0; z-index:-1; border:1px solid color-mix(in srgb, currentColor 55%, transparent); border-radius:999px; background:color-mix(in srgb, currentColor 8%, transparent); opacity:0; transition:opacity 160ms ease; }
.document-knowledge-trigger:hover::before { opacity:1; }
.document-knowledge-trigger__count { color:var(--pm-muted); font-size:11px; }
.document-knowledge-trigger:focus-visible { outline:2px solid var(--pm-accent); outline-offset:4px; }
:global(.pm-no-animations .document-knowledge-trigger::before) { transition:none; }
@media(prefers-reduced-motion:reduce) { .document-knowledge-trigger::before { transition:none; } }
.document-knowledge { width:380px; max-width:calc(100vw - 24px); max-height:calc(100dvh - 32px); overflow-y:auto; padding:20px; border:1px solid var(--pm-divider); border-radius:18px; background:var(--pm-app-surface-raised, #fff); color:var(--pm-text); box-shadow:0 14px 48px rgb(0 0 0 / .2); font-size:12px; line-height:1.5; }
.document-knowledge__header { position:sticky; top:-20px; z-index:2; display:flex; flex-wrap:wrap; justify-content:space-between; align-items:flex-start; gap:0 12px; margin:-20px -20px 18px; padding:20px 20px 0; background:var(--pm-app-surface-raised, #fff); }
.document-knowledge__title-row { display:flex; align-items:center; gap:6px; }
.document-knowledge__info { display:grid; place-items:center; width:28px; height:28px; border-radius:50%; color:var(--pm-muted); }
.document-knowledge__info:hover, .document-knowledge__info--active { color:var(--pm-accent); background:color-mix(in srgb, var(--pm-accent) 8%, transparent); }
.document-knowledge__info:focus-visible { outline:2px solid var(--pm-accent); outline-offset:2px; }
.document-knowledge__header h3 { margin:0; font-size:17px; font-weight:650; letter-spacing:-.02em; }
.document-knowledge__header p { margin:2px 0 0; color:var(--pm-muted); }
.document-knowledge__close { display:grid; place-items:center; flex:0 0 28px; width:28px; height:28px; border-radius:50%; color:var(--pm-muted); }
.document-knowledge__close:hover { background:rgba(var(--v-theme-on-surface), .06); }
.document-knowledge h4 { margin:0 0 8px; font-size:12px; font-weight:650; }
.document-knowledge__state { margin:0 0 16px; padding:12px 14px; border:1px solid var(--pm-divider); border-radius:12px; color:var(--pm-muted); }
.document-knowledge__state--error { border-color:rgba(var(--v-theme-error), .35); }
.document-knowledge__section + .document-knowledge__section { margin-top:18px; }
.document-knowledge__section-heading { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:7px; }
.document-knowledge__section-heading h4 { margin:0; }
.document-knowledge__edit { display:grid; place-items:center; width:28px; height:28px; margin:-5px -5px -5px 0; color:var(--pm-muted); border-radius:8px; }
.document-knowledge__edit:hover:not(:disabled) { color:var(--pm-accent); background:color-mix(in srgb, var(--pm-accent) 8%, transparent); }
.document-knowledge__edit:disabled { opacity:.4; cursor:default; }
.document-knowledge__compact-primary { margin:0; font-weight:600; font-variant-numeric:tabular-nums; overflow-wrap:anywhere; }
.document-knowledge__compact-parties { margin:4px 0 0; color:var(--pm-muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.document-knowledge__disclosure { display:inline-flex; gap:4px; align-items:center; margin-top:8px; color:var(--pm-accent); font-size:11px; font-weight:600; }
.document-knowledge__fields { margin-top:12px; }
.document-knowledge__editor fieldset { border:0; padding:0; margin:0; min-width:0; }
.document-knowledge__editor label { display:block; margin:9px 0 4px; font-size:11px; color:var(--pm-muted); }
.document-knowledge__editor input, .document-knowledge__editor select { display:block; width:100%; min-width:0; height:35px; padding:6px 10px; border:1px solid color-mix(in srgb, var(--pm-muted) 40%, transparent); border-radius:9px; background:color-mix(in srgb, var(--pm-app-surface-raised, #fff) 96%, var(--pm-accent)); color:var(--pm-text); font:inherit; color-scheme:light; }
:global(.v-theme--dark .document-knowledge__editor input), :global(.v-theme--dark .document-knowledge__editor select) { color-scheme:dark; }
.document-knowledge__editor input:focus, .document-knowledge__editor select:focus { outline:2px solid color-mix(in srgb, var(--pm-accent) 25%, transparent); border-color:var(--pm-accent); outline-offset:1px; }
.document-knowledge__money-editor { display:grid; grid-template-columns:minmax(0, 1fr) 80px; gap:10px; }
.document-knowledge__editor-actions { display:flex; justify-content:flex-end; align-items:center; gap:16px; margin-top:12px; }
.document-knowledge__editor-actions > button:first-child { color:var(--pm-muted); }
.document-knowledge__edit-hint { margin:9px 0 0; color:var(--pm-muted); font-size:11px; }
.document-knowledge__saved { margin:6px 0 0; color:var(--pm-success); font-size:11px; }
.document-knowledge__edit:focus-visible, .document-knowledge__disclosure:focus-visible, .document-knowledge__editor-actions button:focus-visible { outline:2px solid var(--pm-accent); outline-offset:2px; }
.document-knowledge__summary-card { padding:12px 14px; border-inline-start:3px solid var(--pm-accent); border-radius:0 12px 12px 0; background:color-mix(in srgb, var(--pm-accent) 6%, transparent); }
.document-knowledge__summary { margin:0; max-height:160px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; }
.document-knowledge__completeness { padding:12px 14px; border:1px solid var(--pm-divider); border-radius:12px; }
.document-knowledge__completeness-heading { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:10px; }
.document-knowledge__completeness-heading h4 { margin:0; }
.document-knowledge__completeness-heading > span { color:var(--pm-muted); font-size:11px; font-variant-numeric:tabular-nums; white-space:nowrap; }
.document-knowledge__segments { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr)); gap:5px; }
.document-knowledge__segment { height:7px; border-radius:999px; background:var(--pm-divider); }
.document-knowledge__segment--filled { background:var(--pm-accent); }
.document-knowledge__fields, .document-knowledge__facts { display:grid; grid-template-columns:auto minmax(0, 1fr); gap:8px 14px; }
.document-knowledge dt { color:var(--pm-muted); }
.document-knowledge dd { margin:0; text-align:right; overflow-wrap:anywhere; }
.document-knowledge__fields dt { align-self:center; }
.document-knowledge__amount { display:flex; align-items:baseline; justify-content:flex-end; gap:5px; font-variant-numeric:tabular-nums; }
.document-knowledge__amount strong { font-size:18px; font-weight:650; line-height:1.3; }
.document-knowledge__amount small { font-size:12px; color:var(--pm-muted); }
.document-knowledge__facts { border-top:1px solid var(--pm-divider); padding-top:16px; margin:18px 0 0; }
.document-knowledge__tags { display:flex; flex-wrap:wrap; gap:6px; }
.document-knowledge__tags span { padding:3px 8px; border:1px solid var(--pm-divider); border-radius:999px; color:var(--pm-text); overflow-wrap:anywhere; max-width:100%; }
.document-knowledge__missing { margin-top:12px; }
.document-knowledge__complete { display:inline-flex; align-items:center; justify-content:center; gap:7px; padding:7px 10px; border:1px solid color-mix(in srgb, var(--pm-accent) 35%, transparent); border-radius:999px; background:color-mix(in srgb, var(--pm-accent) 5%, transparent); color:var(--pm-accent); font:inherit; font-weight:600; cursor:pointer; transition:background-color 160ms ease, border-color 160ms ease; }
.document-knowledge__complete:hover:not(:disabled) { border-color:var(--pm-accent); background:color-mix(in srgb, var(--pm-accent) 10%, transparent); }
.document-knowledge__complete:focus-visible { outline:2px solid var(--pm-accent); outline-offset:3px; }
.document-knowledge__segments:focus-visible { outline:2px solid var(--pm-accent); outline-offset:4px; border-radius:4px; }
.document-knowledge__complete:disabled { cursor:default; opacity:.65; }
.document-knowledge__completion-error { margin:10px 0 0; color:var(--pm-error); }
.document-knowledge--no-motion .document-knowledge__complete { transition:none; }
@media(prefers-reduced-motion:reduce) { .document-knowledge__complete { transition:none; } }
.document-knowledge__status { --knowledge-status-color:var(--pm-muted); display:inline-flex; align-items:center; gap:6px; padding:3px 8px; border:1px solid color-mix(in srgb, var(--knowledge-status-color) 25%, transparent); border-radius:999px; background:color-mix(in srgb, var(--knowledge-status-color) 7%, transparent); color:var(--knowledge-status-color); font-size:11px; font-weight:600; }
.document-knowledge__status::before { content:''; width:5px; height:5px; flex:0 0 5px; border-radius:50%; background:currentColor; }
.document-knowledge__status--done { --knowledge-status-color:var(--pm-success); }
.document-knowledge__status--error { --knowledge-status-color:var(--pm-error); }
.document-knowledge__status--running { --knowledge-status-color:var(--pm-accent); }
.document-knowledge__status--running::before { animation:knowledge-status-pulse 1600ms ease-in-out infinite; }
@keyframes knowledge-status-pulse { 0%, 100% { opacity:1; } 50% { opacity:.35; } }
.document-knowledge--no-motion .document-knowledge__status::before { animation:none; }
@media(prefers-reduced-motion:reduce) { .document-knowledge__status::before { animation:none; } }
.document-knowledge__help { display:flow-root; flex-basis:100%; min-width:0; }
.document-knowledge__help.expand-transition-enter-active, .document-knowledge__help.expand-transition-leave-active { transition:height 200ms ease, opacity 180ms ease !important; }
.document-knowledge__help.expand-transition-enter-from, .document-knowledge__help.expand-transition-leave-to { opacity:0; }
.document-knowledge__explanation { margin-top:12px; padding:12px 14px; border-radius:12px; background:color-mix(in srgb, var(--pm-muted) 6%, transparent); }
.document-knowledge__explanation strong { font-weight:600; }
.document-knowledge__explanation p { margin:4px 0 0; color:var(--pm-muted); }
.document-knowledge__close:focus-visible, .document-knowledge__summary:focus-visible { outline:2px solid var(--pm-accent); outline-offset:3px; border-radius:4px; }
</style>
