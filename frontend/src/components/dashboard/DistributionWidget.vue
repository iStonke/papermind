<!--
  DistributionWidget — Donut der Verteilung, umschaltbar zwischen Tags und
  Dokumenttypen. Segmente werden auf die stärksten gekürzt („Weitere" bündelt
  den Rest).
-->
<template>
  <article class="dash-card dash-donut-card">
    <div class="dash-donut-card__head">
      <h2 class="dash-card__title">Verteilung</h2>
      <div class="dash-toggle" role="group" aria-label="Verteilung umschalten">
        <button
          v-for="m in donutModes"
          :key="m.key"
          type="button"
          class="dash-toggle__btn"
          :class="{ 'dash-toggle__btn--active': donutMode === m.key }"
          @click="donutMode = m.key"
        >{{ m.label }}</button>
      </div>
    </div>
    <div v-if="donutSegments.length" class="dash-donut-card__body">
      <div class="dash-donut" :style="{ '--dash-donut-gradient': donutGradient }">
        <div class="dash-donut__hole">
          <span class="dash-donut__value">{{ formatInt(donutData.total) }}</span>
          <span class="dash-donut__label">{{ donutData.centerLabel }}</span>
        </div>
      </div>
      <ul class="dash-legend">
        <li v-for="(t, i) in donutLegend" :key="`${t.name}-${i}`" class="dash-legend__item">
          <span class="dash-legend__swatch" :style="{ background: rampColor(i, donutLegend.length) }" />
          <span class="dash-legend__name">{{ t.name }}</span>
          <span class="dash-legend__count">{{ formatInt(t.count) }}</span>
        </li>
      </ul>
    </div>
    <p v-else class="dash-card__empty">
      {{ donutMode === 'types' ? 'Noch keine Dokumenttypen vergeben.' : 'Noch keine Tags vergeben.' }}
    </p>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../../stores/dashboard.js';
import { formatInt, rampColor } from './dashboardShared.js';
import './dashboard.css';

// Winkel-Custom-Property für den Uhrzeiger-Aufbau des Donuts registrieren.
// @property-Regeln überleben Vues Style-Pipeline nicht ohne Registrierung, sonst
// interpoliert der Winkel nicht (harter Sprung bei Keyframe-Mitte). Idempotent.
if (typeof CSS !== 'undefined' && typeof CSS.registerProperty === 'function') {
  try {
    CSS.registerProperty({ name: '--dash-donut-sweep', syntax: '<angle>', inherits: false, initialValue: '0deg' });
  } catch { /* bereits registriert */ }
}

const dashboardStore = useDashboardStore();
const { overview } = storeToRefs(dashboardStore);

const donutMode = ref('tags');
const donutModes = [
  { key: 'tags', label: 'Tags' },
  { key: 'types', label: 'Typen' },
];
const DONUT_MAX_SEGMENTS = 6;

const donutData = computed(() => {
  if (donutMode.value === 'types') {
    return {
      segments: overview.value.type_distribution.map((t) => ({ name: t.type, count: t.count })),
      total: overview.value.type_count_total,
      centerLabel: 'Typen',
    };
  }
  return {
    segments: overview.value.tag_distribution.map((t) => ({ name: t.tag, count: t.count })),
    total: overview.value.tag_count_total,
    centerLabel: 'Tags',
  };
});

function compactDonutSegments(segments) {
  const normalized = segments
    .map((t) => ({ name: t.name || 'Ohne Zuordnung', count: Number(t.count || 0) }))
    .filter((t) => t.count > 0);
  if (normalized.length <= DONUT_MAX_SEGMENTS) return normalized;

  const visible = normalized.slice(0, DONUT_MAX_SEGMENTS - 1);
  const rest = normalized
    .slice(DONUT_MAX_SEGMENTS - 1)
    .reduce((sum, t) => sum + t.count, 0);
  return [...visible, { name: 'Weitere', count: rest }];
}

const donutSegments = computed(() => compactDonutSegments(donutData.value.segments));
const donutLegend = computed(() => donutSegments.value);

const donutGradient = computed(() => {
  const segs = donutSegments.value;
  const total = segs.reduce((sum, t) => sum + Number(t.count || 0), 0);
  if (total <= 0) return 'var(--pm-divider)';
  let acc = 0;
  const stops = segs.map((t, i) => {
    const start = (acc / total) * 360;
    acc += Number(t.count || 0);
    const end = (acc / total) * 360;
    return `${rampColor(i, segs.length)} ${start}deg ${end}deg`;
  });
  return `conic-gradient(${stops.join(', ')})`;
});
</script>
