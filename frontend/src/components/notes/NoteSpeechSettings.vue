<template>
  <div class="speech-settings">
    <section class="speech-section">
      <h3>Stimme und Sprache</h3>
      <p>Diese Einstellungen gelten für markierten Text und den Export ganzer Notizen.</p>
      <v-select :model-value="ui.notes_tts_language_mode" :items="SPEECH_LANGUAGES" item-title="label" item-value="value"
        label="Sprachmodus" variant="outlined" density="comfortable" hide-details :disabled="busy"
        @update:model-value="change('notes_tts_language_mode', $event)" />
      <v-select v-if="engineChoices.length > 1" :model-value="options.engine" :items="engineChoices" item-title="label" item-value="value"
        label="Stimmenanbieter" variant="outlined" density="comfortable" hide-details :disabled="busy"
        @update:model-value="option('engine', $event)" />
      <v-select v-if="options.engine === 'piper' && ui.notes_tts_language_mode !== 'en'" :model-value="ui.notes_tts_voice"
        :items="SPEECH_VOICES" item-title="label" item-value="value" label="Deutsche Stimme"
        variant="outlined" density="comfortable" hide-details :disabled="busy"
        @update:model-value="change('notes_tts_voice', $event)" />
      <p class="speech-hint">Englische Abschnitte werden mit einer passenden englischen Stimme vorgelesen.</p>
      <v-alert v-if="!checking && selectedEngine && !selectedEngine.available" type="warning" variant="tonal" density="compact">
        Die Sprachausgabe ist gerade nicht verfügbar. Bitte versuche es später erneut.
      </v-alert>
    </section>

    <section class="speech-section speech-preview">
      <h3>Hörprobe</h3>
      <p>Höre, wie deine gewählte Stimme mit den aktuellen Einstellungen klingt.</p>
      <v-textarea v-model="previewText" label="Text für die Hörprobe" rows="3" maxlength="1200"
        hide-details variant="outlined" />
      <div class="speech-actions">
        <v-btn color="primary" variant="tonal" :disabled="!canPreview || checking || !selectedEngine?.available"
          :loading="preparing" @click="preview">Hörprobe abspielen</v-btn>
        <v-btn v-if="preparing || playing || audioReady" variant="text" @click="stop">Stoppen</v-btn>
      </div>
      <p v-if="preparing" role="status" class="speech-hint">Hörprobe wird vorbereitet …</p>
      <p v-if="previewError" class="speech-error" role="alert">{{ previewError }}</p>
      <audio ref="player" v-show="audioReady" controls class="speech-player" aria-label="Hörprobe abspielen"
        @play="playing = true" @pause="playing = false" @ended="playing = false" />
    </section>

    <section class="speech-section">
      <h3>Sprechrhythmus</h3>
      <div class="speech-range">
        <label for="speech-speed">Tempo <strong>{{ decimal(options.speed) }}×</strong></label>
        <input id="speech-speed" type="range" min="0.6" max="1.5" step="0.05" :value="options.speed" :disabled="busy"
          @change="option('speed', Number($event.target.value))" />
        <span>Langsamer</span><span>Schneller</span>
      </div>
      <div class="speech-range">
        <label for="speech-sentence">Pause zwischen Sätzen <strong>{{ decimal(options.sentence_pause) }} s</strong></label>
        <input id="speech-sentence" type="range" min="0.05" max="0.8" step="0.01" :value="options.sentence_pause" :disabled="busy"
          @change="option('sentence_pause', Number($event.target.value))" />
        <span>Fließend</span><span>Deutlich getrennt</span>
      </div>
      <div class="speech-range">
        <label for="speech-paragraph">Pause zwischen Absätzen <strong>{{ decimal(options.paragraph_pause) }} s</strong></label>
        <input id="speech-paragraph" type="range" :min="Math.max(0.1, options.sentence_pause)" max="1.8" step="0.01"
          :value="options.paragraph_pause" :disabled="busy" @change="option('paragraph_pause', Number($event.target.value))" />
        <span>Kurz</span><span>Länger</span>
      </div>
      <p class="speech-hint">Längere Pausen lassen mehr Zeit zwischen Sätzen und Absätzen.</p>
      <v-btn variant="text" :disabled="busy" @click="resetRhythm">Standardrhythmus wiederherstellen</v-btn>
    </section>

    <section class="speech-section">
      <h3>Aussprache</h3>
      <v-switch :model-value="options.normalize_numbers" label="Zahlen und Einheiten natürlich aussprechen"
        color="primary" hide-details :disabled="busy" @update:model-value="option('normalize_numbers', $event)" />
      <p class="speech-hint">Zum Beispiel Datum, Uhrzeit, „12,5 %“ oder „3 kg“.</p>
      <details class="speech-dictionary">
        <summary>Eigenes Aussprachewörterbuch<span v-if="options.pronunciations.length"> · {{ options.pronunciations.length }} Einträge</span></summary>
        <div class="speech-dictionary-content">
          <p>Lege fest, wie Namen und Fachbegriffe ausgesprochen werden.</p>
          <div v-for="(entry, index) in options.pronunciations" :key="index" class="speech-entry">
            <div class="speech-entry-text"><strong>{{ entry.word }}</strong><span>→ {{ entry.pronunciation }}</span>
              <small>{{ entry.case_sensitive ? 'Groß-/Kleinschreibung beachten' : 'Groß-/Kleinschreibung ignorieren' }}</small></div>
            <v-switch :model-value="entry.enabled" :aria-label="'Aussprache für ' + entry.word + ' aktivieren'" density="compact"
              hide-details color="primary" :disabled="busy" @update:model-value="toggleEntry(index, $event)" />
            <v-btn icon="mdi-pencil-outline" variant="text" size="small" :disabled="busy" :aria-label="'Aussprache für ' + entry.word + ' bearbeiten'" @click="editEntry(index)" />
            <v-btn icon="mdi-delete-outline" variant="text" size="small" :disabled="busy" :aria-label="'Aussprache für ' + entry.word + ' löschen'" @click="removeEntry(index)" />
          </div>
          <form class="speech-dictionary-form" @submit.prevent="saveEntry">
            <v-text-field v-model="word" label="Wort oder Wortgruppe" maxlength="120" hide-details variant="outlined" density="comfortable" :disabled="busy" />
            <v-text-field v-model="pronunciation" label="Gesprochene Form" maxlength="300" hide-details variant="outlined" density="comfortable" :disabled="busy" />
            <v-checkbox v-model="caseSensitive" label="Groß-/Kleinschreibung beachten" hide-details density="compact" :disabled="busy" />
            <div class="speech-actions">
              <v-btn type="submit" variant="tonal" color="primary" :disabled="busy || !word.trim() || !pronunciation.trim() || (editing === null && options.pronunciations.length >= 100)">
                {{ editing === null ? 'Eintrag hinzufügen' : 'Eintrag übernehmen' }}
              </v-btn>
              <v-btn v-if="editing !== null" variant="text" @click="clearEntry">Abbrechen</v-btn>
              <span class="speech-hint">{{ options.pronunciations.length }}/100 Einträge</span>
            </div>
            <p v-if="dictionaryError" class="speech-error" role="alert">{{ dictionaryError }}</p>
          </form>
        </div>
      </details>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { getSpeechEngines, synthesizeSpeech } from '../../api/tts.js';
import { primeSpeechAudio } from '../../utils/ttsAudio.js';
import { defaultSpeechOptions, normalizeSpeechOptions, SPEECH_ENGINE_NAMES, SPEECH_LANGUAGES, SPEECH_VOICES } from '../../utils/speechSettings.js';

const props = defineProps({ ui: { type: Object, required: true }, saving: { type: Object, default: () => ({}) } });
const emit = defineEmits(['change']);
const options = computed(() => normalizeSpeechOptions(props.ui.notes_tts_options));
const busy = computed(() => ['notes_tts_options', 'notes_tts_voice', 'notes_tts_language_mode'].some((key) => props.saving[key]));
const engines = ref(Object.entries(SPEECH_ENGINE_NAMES).map(([id, name]) => ({ id, name, available: false })));
const checking = ref(true);
const selectedEngine = computed(() => engines.value.find((engine) => engine.id === options.value.engine));
const engineChoices = computed(() => engines.value.filter((engine) => engine.available || engine.id === options.value.engine).map((engine) => ({
  value: engine.id, label: engine.name + (engine.available ? '' : ' – nicht verfügbar'),
  props: { disabled: !engine.available && engine.id !== options.value.engine },
})));
const word = ref('');
const pronunciation = ref('');
const caseSensitive = ref(false);
const editing = ref(null);
const dictionaryError = ref('');
const previewText = ref('Guten Tag! Diese Stimme liest deine Notizen vor.\n\nNimm dir einen Moment Zeit und höre, ob Tempo und Pausen für dich angenehm sind.');
const player = ref(null);
const preparing = ref(false);
const playing = ref(false);
const audioReady = ref(false);
const previewError = ref('');
const canPreview = computed(() => previewText.value.trim().length > 0 && previewText.value.length <= 1200 && !preparing.value);
let controller = null;
let objectUrl = null;
let sequence = 0;
let disposed = false;
const decimal = (value) => Number(value || 0).toLocaleString('de-DE', { maximumFractionDigits: 2 });
function change(key, value) { emit('change', { key, value }); }
function option(key, value) {
  const next = normalizeSpeechOptions({ ...options.value, [key]: value });
  if (JSON.stringify(next) !== JSON.stringify(options.value)) change('notes_tts_options', next);
}
function resetRhythm() {
  const defaults = defaultSpeechOptions();
  change('notes_tts_options', { ...options.value, speed: defaults.speed, sentence_pause: defaults.sentence_pause, paragraph_pause: defaults.paragraph_pause });
}
function clearEntry() { word.value = ''; pronunciation.value = ''; caseSensitive.value = false; editing.value = null; dictionaryError.value = ''; }
function editEntry(index) {
  const entry = options.value.pronunciations[index];
  word.value = entry.word; pronunciation.value = entry.pronunciation; caseSensitive.value = entry.case_sensitive; editing.value = index;
}
function saveEntry() {
  const entry = { word: word.value.trim(), pronunciation: pronunciation.value.trim(), case_sensitive: caseSensitive.value, enabled: true };
  if (!entry.word || !entry.pronunciation) return;
  if (/[\r\n\0]/.test(entry.word + entry.pronunciation)) { dictionaryError.value = 'Bitte nur eine Zeile pro Eintrag verwenden.'; return; }
  const list = options.value.pronunciations.map((item) => ({ ...item }));
  if (list.some((item, index) => index !== editing.value && item.case_sensitive === entry.case_sensitive &&
      (entry.case_sensitive ? item.word === entry.word : item.word.toLocaleLowerCase('de-DE') === entry.word.toLocaleLowerCase('de-DE')))) {
    dictionaryError.value = 'Für dieses Wort gibt es bereits einen Eintrag.'; return;
  }
  if (editing.value === null) list.push(entry);
  else { entry.enabled = list[editing.value]?.enabled !== false; list[editing.value] = entry; }
  option('pronunciations', list);
  clearEntry();
}
function toggleEntry(index, enabled) { option('pronunciations', options.value.pronunciations.map((item, i) => i === index ? { ...item, enabled } : item)); }
function removeEntry(index) { option('pronunciations', options.value.pronunciations.filter((_, i) => i !== index)); clearEntry(); }
async function checkEngines() {
  checking.value = true;
  try { const result = await getSpeechEngines(); if (!disposed) engines.value = result.items; }
  catch { if (!disposed) previewError.value = 'Die Sprachausgabe ist gerade nicht erreichbar. Bitte versuche es später erneut.'; }
  finally { if (!disposed) checking.value = false; }
}
function stop() {
  sequence += 1; controller?.abort(); controller = null; preparing.value = false; playing.value = false; audioReady.value = false;
  if (player.value) { player.value.pause(); player.value.removeAttribute('src'); player.value.load(); }
  if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
}
async function preview() {
  if (!canPreview.value || !player.value) return;
  stop(); previewError.value = '';
  const token = sequence;
  const audio = player.value;
  const priming = primeSpeechAudio(audio); // Must run in the direct click, before awaiting the request.
  controller = new AbortController();
  preparing.value = true;
  try {
    const [blob] = await Promise.all([synthesizeSpeech(previewText.value, {
      signal: controller.signal, voice: props.ui.notes_tts_voice || 'standard', languageMode: props.ui.notes_tts_language_mode || 'auto',
      options: options.value,
    }), priming]);
    if (token !== sequence || disposed) return;
    objectUrl = URL.createObjectURL(blob); audio.src = objectUrl; audioReady.value = true; preparing.value = false;
    try { await audio.play(); }
    catch (error) {
      if (token !== sequence) return;
      previewError.value = error?.name === 'NotAllowedError' ? 'Die Hörprobe ist bereit. Starte sie mit dem Wiedergabeknopf.' : 'Die Hörprobe konnte nicht abgespielt werden.';
    }
  } catch (error) {
    if (token === sequence && error?.name !== 'AbortError') previewError.value = error?.message || 'Die Hörprobe konnte nicht erzeugt werden.';
  } finally { if (token === sequence) preparing.value = false; }
}
watch(() => JSON.stringify([props.ui.notes_tts_options, props.ui.notes_tts_voice, props.ui.notes_tts_language_mode, previewText.value]), () => {
  stop(); previewError.value = '';
});
onMounted(checkEngines);
onBeforeUnmount(() => { disposed = true; stop(); });
</script>

<style scoped>
.speech-settings { min-width: 0; }
.speech-section { padding: 24px 0; border-bottom: 1px solid rgba(var(--v-theme-on-surface), .12); display: grid; gap: 14px; }
.speech-section:first-child { padding-top: 8px; }
.speech-section:last-child { border: 0; }
h3 { font-size: 1rem; }
p { margin: 0; font-size: .88rem; line-height: 1.55; color: rgba(var(--v-theme-on-surface), .75); }
.speech-hint { font-size: .8rem; color: rgba(var(--v-theme-on-surface), .65); }
.speech-range { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.speech-range label, .speech-range input { grid-column: 1 / -1; }
.speech-range label { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; font-size: .9rem; }
.speech-range input { width: 100%; accent-color: rgb(var(--v-theme-primary)); min-height: 32px; cursor: pointer; }
.speech-range span { font-size: .75rem; color: rgba(var(--v-theme-on-surface), .6); }
.speech-range span:last-child { text-align: right; }
.speech-dictionary-form { display: grid; gap: 12px; }
.speech-entry { display: flex; align-items: center; gap: 4px; padding: 10px; background: rgba(var(--v-theme-on-surface), .04); border-radius: 8px; }
.speech-entry-text { display: grid; flex: 1; min-width: 0; overflow-wrap: anywhere; font-size: .88rem; }
.speech-entry-text small { font-size: .72rem; opacity: .65; }
.speech-entry :deep(.v-switch) { flex: 0 0 auto; }
.speech-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.speech-player { width: 100%; }
.speech-dictionary summary { cursor: pointer; font-size: .9rem; font-weight: 600; padding: 6px 0; }
.speech-dictionary summary:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 4px; }
.speech-dictionary-content { display: grid; gap: 14px; padding-top: 14px; }
.speech-error { color: rgb(var(--v-theme-error)); }
@media (max-width: 480px) { .speech-entry { flex-wrap: wrap; } .speech-entry-text { flex-basis: 100%; } }
</style>
