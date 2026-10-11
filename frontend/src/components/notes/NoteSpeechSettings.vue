<template>
  <div class="speech-settings">
    <section class="speech-section">
      <h3>Stimme und Sprache</h3>
      <p>Diese Einstellungen gelten für markierten Text und den Export ganzer Notizen. Die Audiodateien werden lokal erzeugt.</p>
      <v-select :model-value="ui.notes_tts_language_mode" :items="SPEECH_LANGUAGES" item-title="label" item-value="value"
        label="Sprachmodus" variant="outlined" density="comfortable" hide-details :disabled="busy"
        @update:model-value="change('notes_tts_language_mode', $event)" />
      <v-select :model-value="options.engine" :items="engineChoices" item-title="label" item-value="value"
        label="Sprachengine" variant="outlined" density="comfortable" hide-details :disabled="busy"
        @update:model-value="option('engine', $event)" />
      <v-select v-if="options.engine === 'piper' && ui.notes_tts_language_mode !== 'en'" :model-value="ui.notes_tts_voice"
        :items="SPEECH_VOICES" item-title="label" item-value="value" label="Deutsche Stimme"
        variant="outlined" density="comfortable" hide-details :disabled="busy"
        @update:model-value="change('notes_tts_voice', $event)" />
      <p class="speech-hint">Englische Abschnitte sprechen alle Engines mit Ryan High (Piper). Die Thorsten-Engines sprechen Deutsch.</p>
      <v-alert v-if="selectedEngine && !selectedEngine.available" type="warning" variant="tonal" density="compact">
        {{ selectedEngine.name }} ist noch nicht verfügbar. Wähle Piper oder richte den lokalen Dienst ein.
      </v-alert>
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
      <p class="speech-hint">Absatzpausen sind mindestens so lang wie Satzpausen. Tempo verändert die Sprechdauer, ohne die Tonhöhe zu verändern.</p>
      <v-btn variant="text" :disabled="busy" @click="resetRhythm">Standardrhythmus wiederherstellen</v-btn>
    </section>

    <section class="speech-section">
      <h3>Aussprache</h3>
      <v-switch :model-value="options.normalize_numbers" label="Zahlen, Datum, Uhrzeit und Einheiten deutsch aussprechen"
        color="primary" hide-details :disabled="busy" @update:model-value="option('normalize_numbers', $event)" />
      <p class="speech-hint">Zum Beispiel „11.10.2026“, „14:30 Uhr“, „12,5 %“ und „3 kg“. URLs und Kennungen bleiben erhalten. Der Notiztext wird dabei nicht verändert.</p>
      <h4>Eigenes Aussprachewörterbuch</h4>
      <p>Namen und Fachbegriffe so schreiben, wie sie klingen sollen. Einträge gelten für ganze Wörter oder Wortgruppen und werden vor der Zahlenaussprache angewendet.</p>
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
    </section>

    <section class="speech-section">
      <h3>Hörprobe und Engine-Vergleich</h3>
      <p>Vergleiche denselben Text mit deinem Tempo und deinen Aussprache-Einstellungen. Erzeugungszeit und Audiolänge zeigen, wie gut die Engine auf der aktuellen Hardware läuft.</p>
      <v-textarea v-model="previewText" label="Text für die Hörprobe" rows="4" maxlength="1200" counter="1200" variant="outlined" />
      <div class="speech-actions">
        <v-btn color="primary" variant="tonal" :disabled="!canPreview || (selectedEngine && !selectedEngine.available)"
          :loading="loadingEngine === options.engine" @click="preview(options.engine)">Hörprobe der gewählten Stimme</v-btn>
        <v-btn v-if="loadingEngine || playing || audioReady" variant="text" @click="stop">Stoppen</v-btn>
        <v-btn variant="text" :loading="checking" :disabled="Boolean(loadingEngine)" @click="checkEngines">Verfügbarkeit prüfen</v-btn>
      </div>
      <p v-if="loadingEngine" role="status">Hörprobe mit {{ SPEECH_ENGINE_NAMES[loadingEngine] }} wird erzeugt …</p>
      <p v-if="previewError" class="speech-error" role="alert">{{ previewError }}</p>
      <audio ref="player" v-show="audioReady" controls class="speech-player" aria-label="Hörprobe abspielen" @play="playing = true" @pause="playing = false" @ended="playing = false" />
      <div class="speech-comparison">
        <article v-for="engine in engines" :key="engine.id" class="speech-engine">
          <div class="speech-engine-heading"><strong>{{ engine.name }}</strong><span>{{ engine.available ? 'Bereit' : 'Nicht verfügbar' }}</span></div>
          <p>{{ engineDescription(engine.id) }}</p>
          <p v-if="metrics[engine.id]" class="speech-metrics">
            {{ decimal(metrics[engine.id].generationMs / 1000) }} s Erzeugung ·
            {{ decimal(metrics[engine.id].duration) }} s Audio
            <span v-if="metrics[engine.id].duration > 0"> · {{ decimal(metrics[engine.id].generationMs / 1000 / metrics[engine.id].duration) }}× Echtzeit</span>
            <span v-if="metrics[engine.id].engine && metrics[engine.id].engine !== engine.id"> · Verwendet: {{ metrics[engine.id].engine }}</span>
          </p>
          <v-btn size="small" variant="outlined" :disabled="!canPreview || !engine.available || Boolean(loadingEngine)"
            @click="preview(engine.id)">Mit {{ engine.name }} hören</v-btn>
        </article>
      </div>
      <p class="speech-hint">Werte beziehen sich auf den aktuellen Testtext. Unter 1× Echtzeit bedeutet: schneller erzeugt als abgespielt. Bei englischem Text wird Piper gemessen. CosyVoice benötigt deutlich mehr Speicher; Kokoro ist der erste Vergleich für CPU-Geräte.</p>
      <p class="speech-hint">Lokale Einrichtung:
        <a href="https://thorsten-voice.de/en/guides/kokoro/" target="_blank" rel="noopener noreferrer">Kokoro</a> ·
        <a href="https://thorsten-voice.de/en/guides/cosyvoice/" target="_blank" rel="noopener noreferrer">CosyVoice</a>.
        Die Einrichtung der Dienste erfolgt auf dem PaperMind-Server.
      </p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { getSpeechEngines, synthesizeSpeechWithMetrics } from '../../api/tts.js';
import { primeSpeechAudio } from '../../utils/ttsAudio.js';
import { defaultSpeechOptions, normalizeSpeechOptions, SPEECH_ENGINE_NAMES, SPEECH_LANGUAGES, SPEECH_VOICES } from '../../utils/speechSettings.js';

const props = defineProps({ ui: { type: Object, required: true }, saving: { type: Object, default: () => ({}) } });
const emit = defineEmits(['change']);
const options = computed(() => normalizeSpeechOptions(props.ui.notes_tts_options));
const busy = computed(() => ['notes_tts_options', 'notes_tts_voice', 'notes_tts_language_mode'].some((key) => props.saving[key]));
const engines = ref(Object.entries(SPEECH_ENGINE_NAMES).map(([id, name]) => ({ id, name, available: false })));
const checking = ref(false);
const selectedEngine = computed(() => engines.value.find((engine) => engine.id === options.value.engine));
const engineChoices = computed(() => engines.value.map((engine) => ({
  value: engine.id, label: engine.name + (engine.available ? '' : ' – nicht verfügbar'),
  props: { disabled: !engine.available && engine.id !== options.value.engine },
})));
const word = ref('');
const pronunciation = ref('');
const caseSensitive = ref(false);
const editing = ref(null);
const dictionaryError = ref('');
const previewText = ref('Am 11.10.2026 treffen wir uns um 14:30 Uhr. Die Strecke ist 3 km lang und die Steigung beträgt 12,5 %.\n\nWir nehmen uns Zeit, sprechen ruhig und setzen passende Pausen.');
const player = ref(null);
const loadingEngine = ref('');
const playing = ref(false);
const audioReady = ref(false);
const previewError = ref('');
const metrics = ref({});
const canPreview = computed(() => previewText.value.trim().length > 0 && previewText.value.length <= 1200 && !loadingEngine.value);
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
function engineDescription(id) {
  return { piper: 'Schnell und sparsam; fünf deutsche Stimmvarianten.',
    kokoro: 'Alternative deutsche Thorsten-Stimme. Läuft auch auf CPUs und ARM-Geräten.',
    cosyvoice: 'Aufwendigere deutsche Sprachsynthese. CPU-Betrieb möglich; mit NVIDIA-GPU deutlich schneller.' }[id];
}
async function checkEngines() {
  checking.value = true;
  try { const result = await getSpeechEngines(); if (!disposed) engines.value = result.items; }
  catch { if (!disposed) previewError.value = 'Die Verfügbarkeit der Sprachengines konnte nicht geprüft werden.'; }
  finally { if (!disposed) checking.value = false; }
}
function stop() {
  sequence += 1; controller?.abort(); controller = null; loadingEngine.value = ''; playing.value = false; audioReady.value = false;
  if (player.value) { player.value.pause(); player.value.removeAttribute('src'); player.value.load(); }
  if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
}
async function preview(engine) {
  if (!canPreview.value || !player.value) return;
  stop(); previewError.value = '';
  const token = sequence;
  const audio = player.value;
  const priming = primeSpeechAudio(audio); // Must run in the direct click, before awaiting the request.
  controller = new AbortController();
  loadingEngine.value = engine;
  try {
    const [result] = await Promise.all([synthesizeSpeechWithMetrics(previewText.value, {
      signal: controller.signal, voice: props.ui.notes_tts_voice || 'standard', languageMode: props.ui.notes_tts_language_mode || 'auto',
      options: { ...options.value, engine },
    }), priming]);
    if (token !== sequence || disposed) return;
    metrics.value = { ...metrics.value, [engine]: result };
    objectUrl = URL.createObjectURL(result.blob); audio.src = objectUrl; audioReady.value = true; loadingEngine.value = '';
    try { await audio.play(); }
    catch (error) {
      if (token !== sequence) return;
      previewError.value = error?.name === 'NotAllowedError' ? 'Die Hörprobe ist bereit. Starte sie mit dem Wiedergabeknopf.' : 'Die Hörprobe konnte nicht abgespielt werden.';
    }
  } catch (error) {
    if (token === sequence && error?.name !== 'AbortError') previewError.value = error?.message || 'Die Hörprobe konnte nicht erzeugt werden.';
  } finally { if (token === sequence) loadingEngine.value = ''; }
}
watch(() => JSON.stringify([props.ui.notes_tts_options, props.ui.notes_tts_voice, props.ui.notes_tts_language_mode, previewText.value]), () => {
  stop(); metrics.value = {}; previewError.value = '';
});
onMounted(checkEngines);
onBeforeUnmount(() => { disposed = true; stop(); });
</script>

<style scoped>
.speech-settings { min-width: 0; }
.speech-section { padding: 24px 0; border-bottom: 1px solid rgba(var(--v-theme-on-surface), .12); display: grid; gap: 14px; }
.speech-section:first-child { padding-top: 8px; }
.speech-section:last-child { border: 0; }
h3 { font-size: 1rem; } h4 { font-size: .9rem; margin-top: 10px; }
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
.speech-comparison { display: grid; gap: 12px; }
.speech-engine { border: 1px solid rgba(var(--v-theme-on-surface), .14); border-radius: 10px; padding: 14px; display: grid; gap: 12px; }
.speech-engine-heading { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; font-size: .9rem; }
.speech-engine-heading span { font-size: .78rem; opacity: .65; }
.speech-engine .v-btn { justify-self: start; max-width: 100%; }
.speech-metrics { font-variant-numeric: tabular-nums; }
.speech-error { color: rgb(var(--v-theme-error)); }
a { color: rgb(var(--v-theme-primary)); }
@media (max-width: 480px) { .speech-entry { flex-wrap: wrap; } .speech-entry-text { flex-basis: 100%; } }
</style>
