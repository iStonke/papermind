<template>
  <div class="doc-calendar">
    <div class="doc-calendar__scroll">
      <div class="doc-calendar__inner">

        <div class="doc-calendar__head">
          <button type="button" class="doc-calendar__nav" aria-label="Voriger Monat" @click="step(-1)">
            <v-icon size="20">mdi-chevron-left</v-icon>
          </button>
          <div class="doc-calendar__title">
            {{ monthName }} {{ year }}
            <span v-if="monthTotal" class="doc-calendar__title-count">· {{ monthTotal }} {{ monthTotal === 1 ? 'Dokument' : 'Dokumente' }}</span>
          </div>
          <button type="button" class="doc-calendar__nav" aria-label="Nächster Monat" @click="step(1)">
            <v-icon size="20">mdi-chevron-right</v-icon>
          </button>
        </div>

        <div class="doc-calendar__grid" :class="{ 'doc-calendar__grid--loading': loading }">
          <div v-for="wd in weekdays" :key="wd" class="doc-calendar__weekday">{{ wd }}</div>
          <span v-for="b in leadingBlanks" :key="`b-${b}`" class="doc-calendar__cell doc-calendar__cell--blank" />
          <button
            v-for="cell in cells"
            :key="cell.day"
            type="button"
            class="doc-calendar__cell"
            :class="{
              'doc-calendar__cell--has': cell.count > 0,
              'doc-calendar__cell--today': cell.isToday,
            }"
            :style="cell.count > 0 ? { background: densityColor(cell.count) } : null"
            :disabled="cell.count === 0"
            :title="cell.count ? `${cell.day}. ${monthName}: ${cell.count} Dokument${cell.count === 1 ? '' : 'e'}` : ''"
            @click="pickDay(cell.day)"
          >
            <span class="doc-calendar__day">{{ cell.day }}</span>
            <span v-if="cell.count > 0" class="doc-calendar__count">{{ cell.count }}</span>
          </button>
        </div>

        <div v-if="availableYears.length" class="doc-calendar__years">
          <button
            v-for="y in availableYears"
            :key="y"
            type="button"
            class="doc-calendar__year"
            :class="{ 'doc-calendar__year--active': y === year }"
            @click="jumpYear(y)"
          >{{ y }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { getDocumentCalendar } from '../api/documents.js';

const props = defineProps({
  // Basis-Filter-Querystring (ohne year/month) – identisch zur Listenansicht.
  filterQuery: { type: String, default: '' },
});

const emit = defineEmits(['pick-day']);

const MONTHS = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
const weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

const today = new Date();
const year = ref(today.getFullYear());
const month = ref(today.getMonth() + 1); // 1-based

const loading = ref(false);
const dayCounts = ref({});        // { day: count }
const monthTotal = ref(0);
const availableYears = ref([]);
const maxDayCount = ref(1);

const monthName = computed(() => MONTHS[month.value - 1]);
const daysInMonth = computed(() => new Date(year.value, month.value, 0).getDate());
const leadingBlanks = computed(() => {
  const firstDow = new Date(year.value, month.value - 1, 1).getDay(); // 0=So
  return (firstDow + 6) % 7; // Woche beginnt Montag
});

const cells = computed(() =>
  Array.from({ length: daysInMonth.value }, (_, i) => {
    const day = i + 1;
    return {
      day,
      count: Number(dayCounts.value[day] || 0),
      isToday: year.value === today.getFullYear() && month.value === today.getMonth() + 1 && day === today.getDate(),
    };
  })
);

function densityColor(count) {
  const t = Math.min(1, count / Math.max(1, maxDayCount.value));
  const share = Math.round(18 + t * 62); // 18%…80% Teal
  return `color-mix(in srgb, var(--pm-accent) ${share}%, transparent)`;
}

async function load() {
  loading.value = true;
  try {
    const params = new URLSearchParams(props.filterQuery);
    params.set('year', String(year.value));
    params.set('month', String(month.value));
    const data = await getDocumentCalendar(params.toString());
    const map = {};
    for (const d of data.days || []) map[d.day] = d.count;
    dayCounts.value = map;
    monthTotal.value = Number(data.month_total || 0);
    availableYears.value = Array.isArray(data.available_years) ? [...data.available_years].sort((a, b) => b - a) : [];
    maxDayCount.value = Math.max(1, ...Object.values(map).map(Number));
  } catch {
    dayCounts.value = {};
    monthTotal.value = 0;
    maxDayCount.value = 1;
  } finally {
    loading.value = false;
  }
}

function step(delta) {
  let m = month.value + delta;
  let y = year.value;
  if (m < 1) { m = 12; y -= 1; }
  if (m > 12) { m = 1; y += 1; }
  month.value = m;
  year.value = y;
}

function jumpYear(y) {
  year.value = y;
}

function pickDay(day) {
  if (!dayCounts.value[day]) return;
  const iso = `${year.value}-${String(month.value).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  emit('pick-day', iso);
}

watch([year, month, () => props.filterQuery], load, { immediate: true });
</script>

<style scoped>
.doc-calendar { height: 100%; min-height: 0; display: flex; flex-direction: column; }
.doc-calendar__scroll { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.doc-calendar__inner { max-width: 560px; margin: 0 auto; padding: 16px 18px 24px; }

.doc-calendar__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.doc-calendar__title {
  font-size: 17px;
  font-weight: 650;
  color: var(--pm-text);
}

.doc-calendar__title-count { font-size: 12.5px; font-weight: 400; color: var(--pm-muted); }

.doc-calendar__nav {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--pm-divider);
  border-radius: 8px;
  background: transparent;
  color: var(--pm-text);
  cursor: pointer;
  transition: background-color 0.14s ease;
}
.doc-calendar__nav:hover { background: rgba(var(--v-theme-on-surface), 0.05); }

.doc-calendar__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6px;
  transition: opacity 0.12s ease;
}
.doc-calendar__grid--loading { opacity: 0.5; }

.doc-calendar__weekday {
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
  color: var(--pm-muted);
  padding-bottom: 2px;
}

.doc-calendar__cell {
  aspect-ratio: 1 / 1;
  border: 1px solid var(--pm-divider);
  border-radius: 8px;
  background: transparent;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  cursor: default;
  color: var(--pm-muted);
  transition: border-color 0.14s ease, transform 0.1s ease;
}

.doc-calendar__cell--blank { border: none; background: transparent; }

.doc-calendar__cell--has {
  cursor: pointer;
  color: var(--pm-text);
  border-color: color-mix(in srgb, var(--pm-accent) 30%, transparent);
}
.doc-calendar__cell--has:hover {
  border-color: var(--pm-accent);
  transform: translateY(-1px);
}

.doc-calendar__cell--today { border-color: color-mix(in srgb, var(--pm-accent) 55%, transparent); }

.doc-calendar__day { font-size: 13px; font-weight: 500; }
.doc-calendar__count {
  font-size: 11px;
  font-weight: 600;
  color: var(--pm-accent-strong, var(--pm-accent));
  font-variant-numeric: tabular-nums;
}

.doc-calendar__years {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--pm-divider);
}

.doc-calendar__year {
  padding: 4px 11px;
  border: 1px solid var(--pm-divider);
  border-radius: 999px;
  background: transparent;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--pm-muted);
  cursor: pointer;
  transition: all 0.14s ease;
}
.doc-calendar__year:hover { color: var(--pm-text); border-color: color-mix(in srgb, var(--pm-text) 22%, transparent); }
.doc-calendar__year--active {
  background: color-mix(in srgb, var(--pm-accent) 14%, transparent);
  border-color: color-mix(in srgb, var(--pm-accent) 40%, transparent);
  color: var(--pm-accent);
}
</style>
