<!--
  CorrespondentMemberTimeline — „Mitglieder im Zeitverlauf“ im Profil einer
  Sammlung: je Mitglied ein Balken vom ersten bis zum letzten Dokument (bei
  wenigen Dokumenten nur Punkte), darunter die Jahresachse. Aktive Mitglieder
  (Kontakt in den letzten zwölf Monaten) tragen die Akzentfarbe.
  Daten aus utils/correspondentProfileStats.js → memberTimelines().
-->
<template>
  <div class="pm-timeline" role="list" :aria-label="label">
    <div v-for="row in visibleRows" :key="row.id" class="pm-timeline__row" role="listitem">
      <button type="button" class="pm-timeline__name" :title="`${row.name} öffnen`" @click="emit('select', row.id)">
        <span class="pm-timeline__label">{{ row.name }}</span>
        <span v-if="row.kind === 'person'" class="pm-timeline__kind">Person</span>
      </button>
      <div class="pm-timeline__track" :title="rangeTitle(row)">
        <span
          v-if="showsBar(row)"
          class="pm-timeline__bar"
          :class="{ 'is-active': row.active }"
          :style="{ left: pos(row.first), width: span(row.first, row.last) }"
        />
        <span
          v-for="(date, index) in showsBar(row) ? [] : row.dates"
          :key="index"
          class="pm-timeline__dot"
          :class="{ 'is-active': row.active }"
          :style="{ left: pos(date) }"
        />
      </div>
      <span class="pm-timeline__count">{{ row.count }}</span>
    </div>
    <div v-if="direct.count" class="pm-timeline__row pm-timeline__row--direct" role="listitem">
      <span class="pm-timeline__name pm-timeline__name--static">
        <span class="pm-timeline__label">Direkt</span>
      </span>
      <div class="pm-timeline__track" :title="`${direct.count} direkt zugeordnet`">
        <span v-for="(date, index) in direct.dates" :key="index" class="pm-timeline__dot pm-timeline__dot--muted" :style="{ left: pos(date) }" />
      </div>
      <span class="pm-timeline__count">{{ direct.count }}</span>
    </div>
    <div class="pm-timeline__row pm-timeline__row--axis" aria-hidden="true">
      <span />
      <div class="pm-timeline__axis">
        <span>{{ startYear }}</span>
        <span v-if="middleYear" class="pm-timeline__middle">{{ middleYear }}</span>
        <span v-if="endYear !== startYear">{{ endYear }}</span>
      </div>
      <span />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  /** Zeilen aus memberTimelines().rows */
  rows: { type: Array, default: () => [] },
  /** memberTimelines().direct */
  direct: { type: Object, default: () => ({ count: 0, dates: [] }) },
  startYear: { type: Number, required: true },
  endYear: { type: Number, required: true },
  label: { type: String, default: 'Mitglieder im Zeitverlauf' },
});
const emit = defineEmits(['select']);

const DAY_MS = 86_400_000;
/** Ab dieser Dauer zeigt ein Mitglied einen Balken statt einzelner Punkte. */
const BAR_MIN_DAYS = 45;

const visibleRows = computed(() => props.rows.filter((row) => row.count > 0));
const middleYear = computed(() =>
  props.endYear - props.startYear > 3 ? Math.round((props.startYear + props.endYear) / 2) : null
);
const rangeStart = computed(() => new Date(props.startYear, 0, 1).getTime());
const rangeEnd = computed(() => new Date(props.endYear + 1, 0, 1).getTime());

function ratio(date) {
  const value = (date.getTime() - rangeStart.value) / (rangeEnd.value - rangeStart.value);
  return Math.min(1, Math.max(0, value));
}
const pos = (date) => `${(ratio(date) * 100).toFixed(2)}%`;
const span = (first, last) => `${Math.max(1.2, (ratio(last) - ratio(first)) * 100).toFixed(2)}%`;
const showsBar = (row) => row.count >= 2 && (row.last - row.first) / DAY_MS >= BAR_MIN_DAYS;

const formatDate = (d) => d.toLocaleDateString('de-DE', { month: '2-digit', year: 'numeric' });
function rangeTitle(row) {
  if (!row.first) return '';
  const range = row.first.getTime() === row.last.getTime() ? formatDate(row.first) : `${formatDate(row.first)} – ${formatDate(row.last)}`;
  return `${row.name}: ${row.count} ${row.count === 1 ? 'Dokument' : 'Dokumente'}, ${range}`;
}
</script>

<style scoped>
.pm-timeline { display: flex; flex-direction: column; container-type: inline-size; }
.pm-timeline__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2.4fr) 24px;
  align-items: center;
  gap: 10px;
  min-height: 32px;
}
.pm-timeline__name {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  padding: 0;
  border: 0;
  background: none;
  color: var(--pm-text);
  font: inherit;
  font-size: 0.88rem;
  text-align: left;
  cursor: pointer;
}
.pm-timeline__name:hover .pm-timeline__label { color: var(--pm-accent-text); }
.pm-timeline__name--static { cursor: default; color: var(--pm-muted); }
.pm-timeline__label { min-width: 0; overflow-wrap: anywhere; }
.pm-timeline__kind { flex: none; color: var(--pm-muted); font-size: 0.74rem; }
.pm-timeline__track {
  position: relative;
  height: 10px;
  border-radius: 3px;
  background: color-mix(in srgb, var(--pm-text) 6%, transparent);
}
.pm-timeline__bar {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 3px;
  background: color-mix(in srgb, var(--pm-text) 45%, transparent);
}
.pm-timeline__bar.is-active { background: var(--pm-accent); }
.pm-timeline__dot {
  position: absolute;
  top: 50%;
  width: 6px;
  height: 6px;
  margin: -3px 0 0 -3px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--pm-text) 62%, transparent);
}
.pm-timeline__dot.is-active { background: var(--pm-accent); }
.pm-timeline__dot--muted { background: color-mix(in srgb, var(--pm-text) 32%, transparent); }
.pm-timeline__count { text-align: right; font-variant-numeric: tabular-nums; color: var(--pm-text); font-size: 0.88rem; }
.pm-timeline__row--axis { min-height: 0; margin-top: 4px; }
.pm-timeline__axis {
  display: flex;
  justify-content: space-between;
  gap: 4px;
  color: var(--pm-muted);
  font-size: 0.74rem;
  font-variant-numeric: tabular-nums;
}
@container (max-width: 380px) {
  .pm-timeline__middle, .pm-timeline__kind { display: none; }
}
</style>
