<template>
  <BaseDialog
    :model-value="modelValue"
    title="Notiz als Audio exportieren"
    header-subtitle="Deine Einstellungen für Sprachausgabe"
    icon="mdi-file-music-outline"
    primary-text="Im Hintergrund erstellen"
    secondary-text="Abbrechen"
    :loading="loading"
    :primary-disabled="!canSubmit"
    max-width="520"
    body-class="note-audio-export-dialog__body"
    @update:model-value="emit('update:modelValue', $event)"
    @primary="submit"
  >
    <div class="note-audio-export-dialog__intro">
      Die Audiodatei wird lokal erzeugt. Im automatischen Modus wechseln deutsche und englische Abschnitte selbstständig die Stimme.
    </div>

    <p class="note-audio-export-dialog__intro">
      {{ speechSummary }}. Stimme, Sprache, Tempo und Aussprache verwaltest du unter Einstellungen → Notizen → Sprachausgabe.
    </p>

    <div class="note-audio-export-dialog__option">
      <div>
        <strong>Titel mitsprechen</strong>
        <span>{{ normalizedTitle || 'Die Notiz hat keinen Titel.' }}</span>
      </div>
      <v-switch
        v-model="includeTitle"
        color="primary"
        density="compact"
        hide-details
        :disabled="!normalizedTitle"
        aria-label="Titel mitsprechen"
      />
    </div>

    <div class="note-audio-export-dialog__summary" aria-live="polite">
      <div>
        <v-icon size="18">mdi-text-long</v-icon>
        <span>{{ characterLabel }}</span>
      </div>
      <div>
        <v-icon size="18">mdi-clock-outline</v-icon>
        <span>{{ durationLabel }}</span>
      </div>
      <div>
        <v-icon size="18">mdi-file-outline</v-icon>
        <span>WAV</span>
      </div>
    </div>

    <v-alert
      v-if="!exportText"
      type="warning"
      variant="tonal"
      density="compact"
      class="note-audio-export-dialog__alert"
    >
      Die Notiz enthält keinen vorlesbaren Text.
    </v-alert>
    <v-alert
      v-else-if="exportText.length > maxCharacters"
      type="error"
      variant="tonal"
      density="compact"
      class="note-audio-export-dialog__alert"
    >
      Der Export umfasst {{ exportText.length.toLocaleString('de-DE') }} Zeichen. Erlaubt sind höchstens
      {{ maxCharacters.toLocaleString('de-DE') }}.
    </v-alert>
  </BaseDialog>
</template>

<script setup>
import { normalizeSpeechOptions, SPEECH_ENGINE_NAMES, SPEECH_LANGUAGES, SPEECH_VOICES } from '../../utils/speechSettings.js';
import { computed, ref, watch } from 'vue';
import BaseDialog from '../BaseDialog.vue';
import { SPEAKING_WPM } from '../../utils/noteStats.js';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  noteTitle: { type: String, default: '' },
  bodyText: { type: String, default: '' },
  defaultVoice: { type: String, default: 'standard' },
  defaultLanguageMode: { type: String, default: 'auto' },
  speechOptions: { type: Object, default: () => ({}) },
  maxCharacters: { type: Number, default: 60000 },
});

const emit = defineEmits(['update:modelValue', 'submit']);

const speechOptions = computed(() => normalizeSpeechOptions(props.speechOptions));
const speechSummary = computed(() => {
  const language = SPEECH_LANGUAGES.find((item) => item.value === props.defaultLanguageMode)?.label || 'Automatisch';
  const voice = SPEECH_VOICES.find((item) => item.value === props.defaultVoice)?.label || 'Klar';
  return [SPEECH_ENGINE_NAMES[speechOptions.value.engine],
    speechOptions.value.engine === 'piper' && props.defaultLanguageMode !== 'en' ? voice : '',
    language, speechOptions.value.speed.toLocaleString('de-DE') + '× Tempo'].filter(Boolean).join(' · ');
});
const includeTitle = ref(true);
const normalizedTitle = computed(() => String(props.noteTitle || '').trim());
const normalizedBody = computed(() => String(props.bodyText || '').trim());
const exportText = computed(() => [includeTitle.value ? normalizedTitle.value : '', normalizedBody.value]
  .filter(Boolean)
  .join('\n\n'));
const canSubmit = computed(() => exportText.value.length > 0 && exportText.value.length <= props.maxCharacters);
const characterLabel = computed(() => `${exportText.value.length.toLocaleString('de-DE')} Zeichen`);
const wordCount = computed(() => exportText.value ? exportText.value.split(/\s+/).filter(Boolean).length : 0);
const durationLabel = computed(() => {
  if (!wordCount.value) return 'Keine Laufzeit';
  const minutes = Math.max(1, Math.ceil(wordCount.value / (SPEAKING_WPM * speechOptions.value.speed)));
  return `ca. ${minutes} ${minutes === 1 ? 'Minute' : 'Minuten'}`;
});

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    includeTitle.value = Boolean(normalizedTitle.value);
  },
);

function submit() {
  if (!canSubmit.value || props.loading) return;
  emit('submit', {
    text: exportText.value,
    title: normalizedTitle.value,
    voice: props.defaultVoice,
    languageMode: props.defaultLanguageMode,
    speechOptions: speechOptions.value,
    includeTitle: includeTitle.value,
  });
}
</script>

<style scoped>
.note-audio-export-dialog__intro {
  color: rgba(var(--v-theme-on-surface), 0.72);
  font-size: 0.9rem;
  line-height: 1.45;
}

.note-audio-export-dialog__voice {
  margin-top: 12px;
}

.note-audio-export-dialog__language {
  margin-top: 18px;
}

.note-audio-export-dialog__option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 62px;
  margin-top: 12px;
  padding: 8px 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 10px;
}

.note-audio-export-dialog__option > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.note-audio-export-dialog__option strong {
  font-size: 0.88rem;
  font-weight: 600;
}

.note-audio-export-dialog__option span {
  overflow: hidden;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 0.76rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.note-audio-export-dialog__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.note-audio-export-dialog__summary > div {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 9px 10px;
  color: rgba(var(--v-theme-on-surface), 0.7);
  background: rgba(var(--v-theme-on-surface), 0.045);
  border-radius: 8px;
  font-size: 0.78rem;
}

.note-audio-export-dialog__alert {
  margin-top: 14px;
}

@media (max-width: 480px) {
  .note-audio-export-dialog__summary {
    grid-template-columns: 1fr;
  }
}
</style>
