<!--
  DocumentsPerYearWidget — Kombidiagramm: Balken je Jahr (nach Dokumentdatum) +
  kumulative Wachstumslinie. Klick auf einen Balken meldet das Jahr über die
  Host-Aktion yearSelect zurück (gedeckelter Startbalken = „Jahr und früher").
-->
<template>
  <article class="dash-card dash-chart">
    <div class="dash-chart__head">
      <div>
        <h2 class="dash-card__title">Dokumente pro Jahr</h2>
        <p class="dash-card__subtitle">{{ yearRangeSubtitle }}</p>
        <div v-if="years.length" class="dash-chart__legend">
          <span class="dash-chart__legend-item"><span class="dash-chart__legend-swatch dash-chart__legend-swatch--bar"></span>pro Jahr</span>
          <span class="dash-chart__legend-item"><span class="dash-chart__legend-swatch dash-chart__legend-swatch--line"></span>kumuliert</span>
          <span v-if="gapCaption" class="dash-chart__gap" :title="`Jahre ohne Dokumente: ${gapYears.join(', ')}`">
            <v-icon size="12">mdi-alert-outline</v-icon>{{ gapCaption }}
          </span>
        </div>
      </div>
      <span class="dash-chart__total">{{ formatInt(cumulativeTotal) }} gesamt</span>
    </div>

    <div v-if="years.length" class="dash-chart__plot">
      <div class="dash-bars">
        <div v-for="(p, i) in years" :key="p.year" class="dash-bars__col">
          <button
            type="button"
            class="dash-bars__bar"
            :class="{
              'dash-bars__bar--current': i === years.length - 1,
              'dash-bars__bar--gap': Number(p.count || 0) === 0,
            }"
            :style="{ height: `${yearBarHeight(p.count)}%` }"
            :title="yearBarTitle(p)"
            :aria-label="p.clipped ? `Dokumente aus ${p.year} und früher anzeigen` : `Dokumente aus ${p.year} anzeigen`"
            @click="actions.yearSelect({ year: p.year, clipped: !!p.clipped })"
          />
        </div>
      </div>
      <svg class="dash-line" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <polyline
          v-if="years.length > 1"
          class="dash-line__path"
          :points="cumulativePoints"
          vector-effect="non-scaling-stroke"
        />
      </svg>
      <span class="dash-line__dot" :style="cumulativeEndStyle" :title="`Gesamt: ${cumulativeTotal}`" />
    </div>
    <p v-else class="dash-card__empty">Noch keine datierten Dokumente.</p>

    <div v-if="years.length" class="dash-bars__axis">
      <span
        v-for="(p, i) in years"
        :key="p.year"
        class="dash-bars__tick"
        :class="{ 'dash-bars__tick--current': i === years.length - 1 }"
      >{{ yearTick(p.year) }}</span>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../../stores/dashboard.js';
import { formatInt, useDashboardActions } from './dashboardShared.js';
import './dashboard.css';

const dashboardStore = useDashboardStore();
const { overview } = storeToRefs(dashboardStore);
const actions = useDashboardActions();

const years = computed(() => overview.value.documents_per_year || []);

const yearRangeSubtitle = computed(() => {
  const arr = years.value;
  if (!arr.length) return 'Nach Dokumentdatum';
  const from = arr[0].year;
  const to = arr[arr.length - 1].year;
  const span = from === to ? `${from}` : `${from}–${to}`;
  return `${span} · nach Dokumentdatum`;
});

const maxYearCount = computed(() =>
  Math.max(1, ...years.value.map((p) => Number(p.count || 0)))
);
const yearBarHeight = (count) => Math.max(2, Math.round((Number(count || 0) / maxYearCount.value) * 100));

// Der gedeckelte Startbalken sammelt zusätzlich alle älteren Dokumente auf und
// wird daher als „<jahr> und früher" ausgewiesen.
const yearBarTitle = (p) => {
  const count = Number(p.count || 0);
  const label = p.clipped ? `${p.year} und früher` : `${p.year}`;
  return count === 0 ? `${label}: keine Dokumente` : `${label}: ${count} Dokumente`;
};

// Bei vielen Jahren die Achse ausdünnen (jedes 2./3. Label), Rand-Jahre immer.
const yearTick = (year) => {
  const arr = years.value;
  const n = arr.length;
  if (n <= 12) return String(year);
  const step = n <= 20 ? 2 : 3;
  const idx = year - arr[0].year;
  const isEdge = idx === 0 || idx === n - 1;
  return isEdge || idx % step === 0 ? String(year) : '';
};

const cumulative = computed(() => {
  let acc = 0;
  return years.value.map((p) => (acc += Number(p.count || 0)));
});
const cumulativeTotal = computed(() => cumulative.value[cumulative.value.length - 1] || 0);

// Linien-Koordinaten im 0..100-viewBox (preserveAspectRatio="none").
// 2 % Rand oben/unten, damit Endpunkt und Nulllinie nicht am Rand kleben.
function cumPointY(i) {
  const max = Math.max(1, cumulativeTotal.value);
  return 100 - (cumulative.value[i] / max) * 96 - 2;
}
function cumPointX(i) {
  const n = years.value.length;
  return n <= 1 ? 50 : ((i + 0.5) / n) * 100;
}
const cumulativePoints = computed(() =>
  years.value.map((_, i) => `${cumPointX(i)},${cumPointY(i)}`).join(' ')
);
const cumulativeEndStyle = computed(() => {
  const i = years.value.length - 1;
  if (i < 0) return { display: 'none' };
  return { left: `${cumPointX(i)}%`, top: `${cumPointY(i)}%` };
});

// Lückenanalyse: Jahre ohne Dokumente in der Historie.
const gapYears = computed(() => {
  const arr = years.value;
  if (arr.length < 2) return [];
  // Innenliegende Null-Jahre (Randjahre haben immer Dokumente per Definition).
  return arr.slice(1, -1).filter((p) => Number(p.count || 0) === 0).map((p) => p.year);
});
const gapCaption = computed(() => {
  const g = gapYears.value;
  if (!g.length) return '';
  if (g.length <= 6) return `Lücken: ${g.join(', ')}`;
  return `${g.length} Jahre ohne Dokumente`;
});
</script>
