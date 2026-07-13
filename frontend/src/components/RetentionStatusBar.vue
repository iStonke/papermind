<template>
  <div class="retention-zone" :class="{ 'retention-zone--open': isEditing }">
    <RetentionChip
      :state="state"
      :badge="badge"
      :open="isEditing"
      :saving="saving"
      @accept="$emit('accept')"
      @toggle="toggleEdit"
    />
    <RetentionForm
      v-if="isEditing"
      v-model:period-years="draft.period_years"
      v-model:paper-original="draft.paper_original"
      v-model:reason="draft.reason"
      :expiry-label="expiryLabel"
      :state="state"
      :saving="saving"
      :suggesting="suggesting"
      :error-message="errorMessage"
      :allow-suggest="allowSuggest"
      :menu-props="menuProps"
      :period-items="retentionPeriodItems"
      @save="onSave"
      @suggest="$emit('suggest')"
      @cancel="cancelEdit"
    />
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue';
import RetentionChip from './RetentionChip.vue';
import RetentionForm from './RetentionForm.vue';

const props = defineProps({
  // Aufbewahrungsdatensatz { status, period_years, paper_original, reason, retain_until } oder null.
  modelValue: { type: Object, default: null },
  // Dokumentdatum als ISO (yyyy-mm-dd) für die Ablaufdatum-Vorschau; leer = keine Vorschau.
  documentDateIso: { type: String, default: '' },
  saving: { type: Boolean, default: false },
  suggesting: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  // KI-Bewertung-Button im Formular anzeigen (im Import steuert die Analyse den Vorschlag).
  allowSuggest: { type: Boolean, default: true },
  // Durchgereichte v-menu-Props für das Auswahlmenü (z. B. Teleport-Ziel im Drawer).
  menuProps: { type: Object, default: () => ({}) }
});

const emit = defineEmits(['accept', 'save', 'suggest']);

const RETENTION_PAPER_PHRASE = Object.freeze({
  unclear: 'Papieroriginal offen',
  keep: 'Original erforderlich',
  scan_sufficient: 'Scan genügt',
  not_applicable: 'Kein Original nötig'
});
const RETENTION_PERIOD_UNLIMITED = -1;
const retentionPeriodItems = Object.freeze([
  { title: 'Unklar', value: null },
  { title: '3 Jahre', value: 3 },
  { title: '6 Jahre', value: 6 },
  { title: '10 Jahre', value: 10 },
  { title: '30 Jahre', value: 30 },
  { title: 'Unbegrenzt', value: RETENTION_PERIOD_UNLIMITED }
]);

const isEditing = ref(false);
const draft = reactive({
  period_years: null,
  paper_original: 'unclear',
  reason: ''
});

function resetDraft(data = props.modelValue) {
  const rawPeriod = data?.period_years;
  draft.period_years = rawPeriod === null || rawPeriod === undefined ? null : Number(rawPeriod);
  draft.paper_original = data?.paper_original || 'unclear';
  draft.reason = data?.reason || '';
}

// Der Parent ersetzt modelValue nach jeder erfolgreichen Aktion (Speichern/Übernehmen/
// KI-Bewertung) und beim Dokumentwechsel: Entwurf nachziehen und Formular schließen.
// Ein Fehler lässt modelValue unverändert -> Formular bleibt offen und zeigt errorMessage.
watch(() => props.modelValue, () => {
  resetDraft();
  isEditing.value = false;
}, { immediate: true });

// Beim Aufklappen den Entwurf frisch aus modelValue setzen (gilt inline wie Popover).
watch(isEditing, (open) => {
  if (open) resetDraft();
});

// Drei Anzeigezustände (Vorlage 1a): leer / KI-Vorschlag / befüllt.
const state = computed(() => {
  const status = props.modelValue?.status;
  if (status === 'suggested') return 'ai';
  if (status === 'accepted' || status === 'manual') return 'filled';
  return 'empty';
});

function formatPeriod(period) {
  if (period === RETENTION_PERIOD_UNLIMITED) return 'Unbegrenzt';
  const years = Number(period);
  if (Number.isFinite(years) && years > 0) return `${years} Jahre`;
  return 'Erfasst';
}

// ISO (yyyy-mm-dd) -> dd.mm.yyyy für die Anzeige.
function isoToDisplay(iso) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  return match ? `${match[3]}.${match[2]}.${match[1]}` : '';
}

const badge = computed(() => {
  const data = props.modelValue;
  if (state.value === 'empty') {
    return { icon: 'mdi-shield-outline', title: 'Nicht erfasst', subtitle: 'Aufbewahrungspflicht ergänzen' };
  }
  const title = formatPeriod(data?.period_years);
  const phrase = RETENTION_PAPER_PHRASE[data?.paper_original] || RETENTION_PAPER_PHRASE.unclear;
  if (state.value === 'ai') {
    return { icon: 'mdi-creation', title, subtitle: `${phrase} · zur Prüfung` };
  }
  let expiry;
  if (data?.retain_until) {
    expiry = `bis ${isoToDisplay(data.retain_until) || data.retain_until}`;
  } else if (data?.period_years === RETENTION_PERIOD_UNLIMITED) {
    expiry = 'kein Ablauf';
  } else {
    expiry = 'ohne Ablaufdatum';
  }
  return { icon: 'mdi-shield-outline', title, subtitle: `${phrase} · ${expiry}` };
});

// Ablaufdatum leitet sich (wie serverseitig) aus Dokumentdatum + gewählter Frist ab.
const expiryLabel = computed(() => {
  const period = draft.period_years;
  if (period === RETENTION_PERIOD_UNLIMITED) return 'Kein Ablauf';
  const years = Number(period);
  if (!Number.isFinite(years) || years <= 0) return '';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(props.documentDateIso || ''));
  if (!match) return '';
  const [, y, m, d] = match.map(Number);
  const target = new Date(y + years, m - 1, d);
  if (target.getMonth() !== m - 1) target.setDate(0); // 29.02. -> 28.02. im Nicht-Schaltjahr
  const dd = String(target.getDate()).padStart(2, '0');
  const mm = String(target.getMonth() + 1).padStart(2, '0');
  return `${dd}.${mm}.${target.getFullYear()}`;
});

function toggleEdit() {
  isEditing.value = !isEditing.value;
}

function cancelEdit() {
  isEditing.value = false;
}

function onSave() {
  emit('save', {
    period_years: draft.period_years === null || draft.period_years === '' ? null : Number(draft.period_years),
    paper_original: draft.paper_original || 'unclear',
    reason: draft.reason || null
  });
}
</script>

<style>
.retention-zone {
  --retention-amber: 224, 171, 75;      /* #e0ab4b */
  margin: 16px 0 16px;
  max-width: 620px;
  border-radius: 10px;
}

.retention-zone--open {
  overflow: hidden;
  background: var(--pm-detail-info-bg);
  border: 1px solid var(--pm-detail-info-border);
}

.retention-bar {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 12px;
  background: var(--pm-detail-info-bg);
  border: 1px solid var(--pm-detail-info-border);
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.16s ease, background-color 0.16s ease;
}

.retention-zone--open .retention-bar {
  border: 1px solid transparent;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 10px 10px 0 0;
  background: transparent;
}

.retention-bar:hover {
  border-color: var(--pm-detail-field-hover-border);
}

.retention-zone--open .retention-bar:hover {
  border-color: transparent;
  border-bottom-color: rgba(var(--v-theme-on-surface), 0.06);
}

.retention-bar:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.4);
  outline-offset: 1px;
}

/* Icon-Badge links (28×28), Farbe je Zustand. */
.retention-bar__badge {
  width: 28px;
  height: 28px;
  flex: none;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.retention-bar__badge .v-icon {
  color: inherit;
}

.retention-bar--filled .retention-bar__badge {
  background: rgba(var(--retention-amber), 0.14);
  color: rgb(var(--retention-amber));
}

.retention-bar--empty .retention-bar__badge {
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.22);
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.retention-bar--ai .retention-bar__badge {
  background: rgba(var(--v-theme-primary), 0.14);
  color: rgb(var(--v-theme-primary));
}

.retention-bar__text {
  flex: 1;
  min-width: 0;
}

.retention-bar__title-row {
  display: flex;
  align-items: center;
  gap: 7px;
}

.retention-bar__title {
  font-weight: 600;
  font-size: 0.845rem;
  color: rgb(var(--v-theme-on-surface));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.retention-bar--empty .retention-bar__title {
  color: rgba(var(--v-theme-on-surface), 0.72);
}

.retention-bar__ki {
  flex: none;
  font-weight: 600;
  font-size: 0.6rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.16);
  border-radius: 5px;
  padding: 2px 6px;
  white-space: nowrap;
}

.retention-bar__subtitle {
  margin-top: 1px;
  font-size: 0.75rem;
  color: rgba(var(--v-theme-on-surface), 0.56);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.retention-bar__accept {
  flex: none;
  font-weight: 600;
  font-size: 0.75rem;
  color: rgb(var(--v-theme-primary));
  background: transparent;
  border: none;
  padding: 2px 4px;
  cursor: pointer;
  white-space: nowrap;
}

.retention-bar__accept:disabled {
  opacity: 0.5;
  cursor: default;
}

.retention-bar__pencil {
  flex: none;
  display: inline-flex;
  padding: 4px;
  color: rgba(var(--v-theme-on-surface), 0.45);
}

.retention-bar__chev {
  flex: none;
  color: rgba(var(--v-theme-on-surface), 0.45);
  transition: transform 0.2s ease;
}

.retention-bar__chev--open {
  transform: rotate(180deg);
}

/* Ausgeklapptes Formular – dockt nahtlos unter der Leiste an. */
.retention-form {
  background: var(--pm-detail-info-bg);
  border: 0;
  border-radius: 0 0 10px 10px;
  margin: 0;
  padding: 12px 14px 13px;
}

.retention-form__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.retention-form__field {
  display: flex;
  flex-direction: column;
}

.retention-form__field label {
  font-size: 0.72rem;
  color: rgba(var(--v-theme-on-surface), 0.58);
  margin-bottom: 6px;
}

.retention-form__static {
  display: flex;
  align-items: center;
  min-height: 34px;
  padding: 0 10px;
  background: var(--pm-detail-field-bg);
  border: 1px solid var(--pm-detail-field-border);
  border-radius: 8px;
  font-size: 0.85rem;
  color: rgba(var(--v-theme-on-surface), 0.82);
}

/* Formular-Inputs: gefüllte Box mit eigenem Rahmen (Vorlage) statt Plain. */
.retention-form .v-field {
  background: var(--pm-detail-field-bg) !important;
  border: 1px solid var(--pm-detail-field-border) !important;
  border-radius: 8px !important;
}

.retention-form .v-field--variant-outlined .v-field__outline {
  display: none !important;
}

.retention-form .v-field--focused {
  border-color: var(--pm-detail-field-focus-border) !important;
}

.retention-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--pm-detail-field-bg);
  border: 1px solid var(--pm-detail-field-border);
  border-radius: 8px;
  padding: 9px 12px;
  margin-bottom: 12px;
}

.retention-toggle-row__title {
  font-weight: 600;
  font-size: 0.78rem;
  color: rgb(var(--v-theme-on-surface));
}

.retention-toggle-row__hint {
  margin-top: 1px;
  font-size: 0.69rem;
  color: rgba(var(--v-theme-on-surface), 0.56);
}

/* iOS-artiger Schalter (40×23). */
.retention-toggle {
  position: relative;
  width: 40px;
  height: 23px;
  flex: none;
  padding: 0;
  border: none;
  border-radius: 12px;
  background: rgba(var(--v-theme-on-surface), 0.22);
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.retention-toggle--on {
  background: rgb(var(--v-theme-primary));
}

.retention-toggle__knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 19px;
  height: 19px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s ease;
}

.retention-toggle--on .retention-toggle__knob {
  transform: translateX(17px);
}

.retention-form__error {
  color: rgb(var(--v-theme-error));
  font-size: 0.75rem;
  margin-bottom: 8px;
}

.retention-form__disclaimer {
  color: rgba(var(--v-theme-on-surface), 0.48);
  font-size: 0.66rem;
  line-height: 1.35;
  margin-bottom: 10px;
}

.retention-form__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.retention-form__ai {
  margin-right: auto;
}

/* Vorlage nutzt Satz- statt Großschreibung; Vuetify-Defaults zurücknehmen. */
.retention-form__actions .v-btn {
  text-transform: none;
  letter-spacing: normal;
}

.retention-form__cancel {
  color: rgba(var(--v-theme-on-surface), 0.62) !important;
}

.retention-form__save {
  border-radius: 8px;
}
</style>
