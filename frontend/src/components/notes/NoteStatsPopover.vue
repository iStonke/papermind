<template>
  <v-menu
    v-model="open"
    location="top end"
    :offset="8"
    :close-on-content-click="false"
    content-class="pm-menu note-stats"
  >
    <template #activator="{ props: menuProps }">
      <button
        v-bind="menuProps"
        type="button"
        class="note-stats__trigger"
        title="Textstatistik anzeigen"
        :aria-label="`${label}. Textstatistik anzeigen`"
      >{{ label }}</button>
    </template>

    <div v-if="stats" class="note-stats__body" role="dialog" aria-label="Textstatistik">
      <header class="note-stats__head">
        <span>Textstatistik</span>
        <span v-if="stats.selection" class="note-stats__scope">Markierung</span>
      </header>

      <div class="note-stats__kpis">
        <div v-for="kpi in kpis" :key="kpi.label" class="note-stats__kpi">
          <strong>{{ kpi.value }}</strong>
          <span>{{ kpi.label }}</span>
        </div>
      </div>

      <dl class="note-stats__rows">
        <div><dt>Zeichen ohne Leerzeichen</dt><dd>{{ num(stats.charactersNoSpaces) }}</dd></div>
        <div><dt>Lesezeit</dt><dd>{{ minutes(stats.readingMinutes) }}</dd></div>
        <div><dt>Sprechzeit</dt><dd>{{ minutes(stats.speakingMinutes) }}</dd></div>
      </dl>

      <section class="note-stats__section">
        <h4>Lesbarkeit</h4>
        <div v-if="stats.readabilityBand" class="note-stats__score" :class="`is-${stats.readabilityBand.key}`">
          <div class="note-stats__score-line">
            <span>{{ stats.readabilityBand.label }}</span>
            <strong>{{ stats.readability }}<small> / 100</small></strong>
          </div>
          <div class="note-stats__meter" aria-hidden="true">
            <span :style="{ width: `${stats.readability}%` }"></span>
          </div>
          <p class="note-stats__hint">Flesch-Index (deutsch) · höher = leichter</p>
        </div>
        <p v-else class="note-stats__hint">Zu wenig Text für einen Lesbarkeitswert.</p>
        <dl class="note-stats__rows">
          <div><dt>Ø Satzlänge</dt><dd>{{ decimal(stats.avgSentenceWords) }} Wörter</dd></div>
        </dl>
        <button
          v-if="stats.longestSentence && stats.sentences > 1"
          type="button"
          class="note-stats__longest"
          title="Zum längsten Satz springen"
          @click="jumpToLongest"
        >
          <span class="note-stats__longest-label">
            Längster Satz · {{ stats.longestSentence.words }} Wörter
            <v-icon size="13">mdi-arrow-right</v-icon>
          </span>
          <span class="note-stats__longest-text">{{ stats.longestSentence.text }}</span>
        </button>
      </section>

      <section class="note-stats__section">
        <h4>Wortschatz</h4>
        <dl class="note-stats__rows">
          <div><dt>Verschiedene Wörter</dt><dd>{{ num(stats.uniqueWords) }}</dd></div>
          <div>
            <dt title="Anteil verschiedener Wörter an allen Wörtern. Sinkt bei längeren Texten natürlich.">Wortschatzvielfalt</dt>
            <dd>{{ percent(stats.lexicalDiversity) }}</dd>
          </div>
          <div><dt>Ø Wortlänge</dt><dd>{{ decimal(stats.avgWordLetters) }} Buchstaben</dd></div>
          <div><dt>Lange Wörter (7+ Buchstaben)</dt><dd>{{ percent(stats.longWordShare) }}</dd></div>
        </dl>
      </section>
    </div>
  </v-menu>
</template>

<script setup>
import { computed, ref, watch } from 'vue';

const props = defineProps({
  label: { type: String, required: true },
  /** Liefert die Statistik (computeNoteStats) für Notiz bzw. Markierung. */
  compute: { type: Function, required: true },
});
const emit = defineEmits(['jump']);

const open = ref(false);
const stats = ref(null);

// Nur beim Öffnen rechnen – die Statistik ist eine Momentaufnahme, kein
// Live-Wert pro Anschlag.
watch(open, (value) => {
  if (value) stats.value = props.compute();
});

const numberFormat = new Intl.NumberFormat('de-DE');
const decimalFormat = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 });
const percentFormat = new Intl.NumberFormat('de-DE', { style: 'percent', maximumFractionDigits: 0 });
const num = value => numberFormat.format(value || 0);
const decimal = value => decimalFormat.format(value || 0);
const percent = value => percentFormat.format(value || 0);
const minutes = value => (value ? `~ ${value} Min.` : '–');

const kpis = computed(() => {
  const s = stats.value;
  if (!s) return [];
  return [
    { label: s.words === 1 ? 'Wort' : 'Wörter', value: num(s.words) },
    { label: 'Zeichen', value: num(s.characters) },
    { label: s.sentences === 1 ? 'Satz' : 'Sätze', value: num(s.sentences) },
    { label: s.paragraphs === 1 ? 'Absatz' : 'Absätze', value: num(s.paragraphs) },
  ];
});

function jumpToLongest() {
  const longest = stats.value?.longestSentence;
  if (!longest) return;
  open.value = false;
  emit('jump', { from: longest.from, to: longest.to });
}
</script>

<style scoped>
.note-stats__trigger {
  font: inherit;
  color: inherit;
  background: none;
  border: 0;
  padding: 1px 6px;
  margin: -1px -6px;
  border-radius: 6px;
  cursor: pointer;
  font-variant-numeric: tabular-nums;
  transition: background-color var(--pm-motion-fast, 120ms) ease, color var(--pm-motion-fast, 120ms) ease;
}
.note-stats__trigger:hover,
.note-stats__trigger:focus-visible,
.note-stats__trigger[aria-expanded='true'] {
  background: color-mix(in srgb, var(--pm-accent) 10%, transparent);
  color: var(--pm-text);
  outline: none;
}
</style>

<style>
/* Teleportiertes Menü: unscoped, aber vollständig unter .note-stats. */
.note-stats.pm-menu {
  padding: 0;
  width: 300px;
  max-width: calc(100vw - 32px);
}
.note-stats__body {
  padding: 12px 14px 14px;
  color: var(--pm-text);
  font-size: 0.78rem;
}
.note-stats__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-weight: 600;
  font-size: 0.8rem;
}
.note-stats__scope {
  padding: 1px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-accent) 14%, transparent);
  color: var(--pm-accent-text, var(--pm-accent));
  font-size: 0.68rem;
  font-weight: 600;
}
.note-stats__kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-bottom: 10px;
}
.note-stats__kpi {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 7px 2px 6px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--pm-text) 4%, transparent);
}
.note-stats__kpi strong {
  font-size: 0.95rem;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.note-stats__kpi span {
  color: var(--pm-muted);
  font-size: 0.66rem;
}
.note-stats__rows {
  margin: 0;
}
.note-stats__rows > div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 3px 0;
}
.note-stats__rows dt {
  color: var(--pm-muted);
}
.note-stats__rows dt[title] {
  cursor: help;
  text-decoration: underline dotted color-mix(in srgb, var(--pm-muted) 60%, transparent);
  text-underline-offset: 3px;
}
.note-stats__rows dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.note-stats__section {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--pm-divider);
}
.note-stats__section h4 {
  margin: 0 0 6px;
  color: var(--pm-muted);
  font-size: 0.66rem;
  font-weight: 650;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.note-stats__score {
  --note-stats-band: rgb(var(--v-theme-success));
  margin-bottom: 6px;
}
.note-stats__score.is-medium { --note-stats-band: var(--pm-accent); }
.note-stats__score.is-hard { --note-stats-band: rgb(var(--v-theme-warning)); }
.note-stats__score.is-very-hard { --note-stats-band: rgb(var(--v-theme-error)); }
.note-stats__score-line {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.note-stats__score-line strong {
  font-variant-numeric: tabular-nums;
}
.note-stats__score-line small {
  color: var(--pm-muted);
  font-weight: 400;
}
.note-stats__meter {
  height: 5px;
  margin: 5px 0 4px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-text) 8%, transparent);
  overflow: hidden;
}
.note-stats__meter span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--note-stats-band);
}
.note-stats__hint {
  margin: 0;
  color: var(--pm-muted);
  font-size: 0.7rem;
}
.note-stats__longest {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  margin-top: 6px;
  padding: 7px 9px;
  border: 1px solid var(--pm-divider);
  border-radius: 8px;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color var(--pm-motion-fast, 120ms) ease, background-color var(--pm-motion-fast, 120ms) ease;
}
.note-stats__longest:hover,
.note-stats__longest:focus-visible {
  border-color: color-mix(in srgb, var(--pm-accent) 50%, transparent);
  background: color-mix(in srgb, var(--pm-accent) 6%, transparent);
  outline: none;
}
.note-stats__longest-label {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--pm-muted);
  font-size: 0.7rem;
}
.note-stats__longest-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 0.74rem;
  line-height: 1.35;
}
</style>
