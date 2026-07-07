<template>
  <section class="dashboard" aria-label="Übersicht">
    <div class="dashboard__scroll">
      <!-- 1) Kopfzeile -->
      <header class="dash-head">
        <div class="dash-head__intro">
          <h1 class="dash-head__greeting">{{ greeting }}</h1>
          <p class="dash-head__meta">{{ headMeta }}</p>
        </div>
        <div class="dash-head__actions">
          <button type="button" class="dash-btn dash-btn--primary" @click="emit('open-import')">
            <v-icon size="15">mdi-tray-arrow-up</v-icon>
            Importieren
          </button>
          <button type="button" class="dash-btn" @click="emit('open-ai')">
            <v-icon size="15">mdi-creation</v-icon>
            KI fragen
          </button>
        </div>
      </header>

      <!-- Leerer Zustand -->
      <div v-if="isEmpty" class="dash-empty">
        <div class="dash-empty__icon"><v-icon size="34">mdi-view-dashboard-outline</v-icon></div>
        <h2 class="dash-empty__title">Noch keine Dokumente</h2>
        <p class="dash-empty__text">Sobald du dein erstes Dokument ablegst, erscheinen hier Kennzahlen und Auswertungen.</p>
        <button type="button" class="dash-btn dash-btn--primary dash-empty__cta" @click="emit('open-import')">
          <v-icon size="16">mdi-tray-arrow-up</v-icon>
          Erstes Dokument importieren
        </button>
      </div>

      <template v-else>
        <!-- 2) Kennzahlen-Band -->
        <div class="dash-stats" :class="{ 'is-loading': showSkeleton }">
          <article
            v-for="card in statCards"
            :key="card.key"
            class="dash-card dash-stat"
            :class="{ 'dash-stat--clickable': card.attentionKey }"
            :role="card.attentionKey ? 'button' : undefined"
            :tabindex="card.attentionKey ? 0 : undefined"
            @click="handleStatCardClick(card)"
            @keydown.enter.prevent="handleStatCardClick(card)"
            @keydown.space.prevent="handleStatCardClick(card)"
          >
            <div class="dash-stat__head">
              <span class="dash-stat__label">{{ card.label }}</span>
              <v-icon size="16" class="dash-stat__icon">{{ card.icon }}</v-icon>
            </div>
            <div class="dash-stat__value">
              {{ card.value }}<span v-if="card.unit" class="dash-stat__unit">{{ card.unit }}</span>
            </div>

            <!-- Trend / Sparkline / Progress je nach Karte -->
            <div v-if="card.key === 'this_month'" class="dash-spark" aria-hidden="true">
              <span
                v-for="(h, i) in sparkline"
                :key="i"
                class="dash-spark__bar"
                :class="{ 'dash-spark__bar--current': i === sparkline.length - 1 }"
                :style="{ height: `${h}%` }"
              />
            </div>
            <div v-else class="dash-stat__trend" :class="card.trendClass">
              <v-icon v-if="card.trendIcon" size="13">{{ card.trendIcon }}</v-icon>
              {{ card.sub }}
            </div>
          </article>
        </div>

        <!-- 3) Visualisierungen -->
        <div class="dash-viz">
          <!-- Jahres-Kombidiagramm: Balken (pro Jahr) + kumulative Wachstumslinie -->
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
                    @click="emit('year-select', { year: p.year, clipped: !!p.clipped })"
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

          <!-- Rechte Spalte -->
          <div class="dash-viz__side">
            <!-- Top-Korrespondenten -->
            <article class="dash-card dash-rank">
              <h2 class="dash-card__title">Top-Korrespondenten</h2>
              <div v-if="topCorrespondents.length" ref="rankListEl" class="dash-rank__list">
                <div v-for="(c, i) in visibleTopCorrespondents" :key="c.name" class="dash-rank__row">
                  <div class="dash-rank__meta">
                    <span class="dash-rank__name">{{ c.name }}</span>
                    <span class="dash-rank__count">{{ formatInt(c.count) }}</span>
                  </div>
                  <div class="dash-rank__track">
                    <span
                      class="dash-rank__fill"
                      :style="{ width: `${rankPct(c.count)}%`, background: rampColor(i, topCorrespondents.length) }"
                    />
                  </div>
                </div>
              </div>
              <p v-else class="dash-card__empty">Noch keine Korrespondenten zugeordnet.</p>
            </article>

          </div>
        </div>

        <!-- 4) Untere Inhalte -->
        <div class="dash-lower">
          <div class="dash-lower__main">
            <div class="dash-recent">
              <div class="dash-recent__head">
                <h2 class="dash-card__title">Zuletzt importiert</h2>
                <button type="button" class="dash-link" @click="emit('show-all-recent')">Alle anzeigen</button>
              </div>
              <div v-if="overview.recent.length" class="dash-recent__grid">
                <button
                  v-for="doc in overview.recent"
                  :key="doc.id"
                  type="button"
                  class="dash-card dash-doc"
                  @click="emit('open-document', doc.id)"
                >
                  <span class="dash-doc__thumb">
                    <img
                      v-if="!thumbError[doc.id]"
                      :src="thumbUrl(doc.id)"
                      alt=""
                      loading="lazy"
                      @error="thumbError[doc.id] = true"
                    />
                    <v-icon v-else size="20">mdi-file-outline</v-icon>
                  </span>
                  <span class="dash-doc__text">
                    <span class="dash-doc__title">{{ doc.title }}</span>
                    <span class="dash-doc__corr">{{ doc.correspondent || 'Ohne Korrespondent' }}</span>
                    <span class="dash-doc__date">{{ formatDate(doc.date) }}</span>
                  </span>
                </button>
              </div>
              <p v-else class="dash-card__empty">Noch keine Dokumente vorhanden.</p>
            </div>

            <!-- Top-Suchbegriffe -->
            <article class="dash-card dash-searches">
              <h2 class="dash-card__title">Häufig gesucht</h2>
              <ul v-if="topSearches.length" class="dash-searches__list">
                <li v-for="(s, i) in topSearches" :key="s.term" class="dash-searches__row">
                  <button type="button" class="dash-searches__term" :title="s.term" @click="emit('search-term', s.term)">
                    <v-icon size="13" class="dash-searches__icon">mdi-magnify</v-icon>
                    <span class="dash-searches__label">{{ s.term }}</span>
                    <span class="dash-searches__count">{{ formatInt(s.count) }}</span>
                  </button>
                  <div class="dash-searches__track">
                    <span class="dash-searches__fill" :style="{ width: `${searchPct(s.count)}%`, background: rampColor(i, topSearches.length) }" />
                  </div>
                </li>
              </ul>
              <p v-else class="dash-card__empty">Noch keine Suchen erfasst.</p>
            </article>
          </div>

          <div class="dash-lower__side">
            <!-- Verteilung: Tags ↔ Dokumenttypen -->
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
          </div>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../stores/auth.js';
import { useDashboardStore } from '../stores/dashboard.js';
import { documentThumbnailUrl } from '../api/documents.js';

// Winkel-Custom-Property für den Uhrzeiger-Aufbau des Donuts registrieren.
// @property-Regeln überleben Vues scoped-Style-Pipeline nicht, ohne Registrierung
// interpoliert der Winkel nicht (harter Sprung bei Keyframe-Mitte). Idempotent.
if (typeof CSS !== 'undefined' && typeof CSS.registerProperty === 'function') {
  try {
    CSS.registerProperty({ name: '--dash-donut-sweep', syntax: '<angle>', inherits: false, initialValue: '0deg' });
  } catch { /* bereits registriert */ }
}

const emit = defineEmits([
  'open-import',
  'open-ai',
  'open-document',
  'attention-select',
  'show-all-recent',
  'search-term',
  'year-select',
]);

const dashboardStore = useDashboardStore();
const auth = useAuthStore();
const { overview, isLoading, hasLoadedOnce } = storeToRefs(dashboardStore);
const rankListEl = ref(null);
const visibleRankCount = ref(6);
let rankResizeObserver = null;

onMounted(() => {
  void dashboardStore.fetchOverview();
});

onBeforeUnmount(() => {
  rankResizeObserver?.disconnect();
});

const showSkeleton = computed(() => isLoading.value && !hasLoadedOnce.value);
const isEmpty = computed(() => hasLoadedOnce.value && overview.value.stats.documents_total === 0);

// ── Formatierung ────────────────────────────────────────────────────────────
const intFormatter = new Intl.NumberFormat('de-DE');
const formatInt = (n) => intFormatter.format(Number(n || 0));

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// ── Kopfzeile ───────────────────────────────────────────────────────────────
const userGreetingName = computed(() => {
  const name = auth.user?.display_name || auth.username;
  return String(name || '').trim();
});

const greeting = computed(() => {
  const h = new Date().getHours();
  const part = h < 5 ? 'Gute Nacht' : h < 11 ? 'Guten Morgen' : h < 18 ? 'Guten Tag' : 'Guten Abend';
  return userGreetingName.value ? `${part}, ${userGreetingName.value}` : part;
});

const headMeta = computed(() =>
  new Date().toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
);

// ── Kennzahlen-Karten ───────────────────────────────────────────────────────
const statCards = computed(() => {
  const s = overview.value.stats;
  const documentsTotal = Number(s.documents_total || 0);
  const withoutDocumentType = Math.min(
    documentsTotal,
    Math.max(0, Number(overview.value.attention?.without_document_type || 0))
  );
  const withoutDocumentTypePct = documentsTotal > 0
    ? Math.round((withoutDocumentType / documentsTotal) * 100)
    : 0;
  const trendPct = s.total_trend_pct;
  const hasTrend = trendPct !== null && trendPct !== undefined;
  const trendUp = hasTrend && trendPct >= 0;

  return [
    {
      key: 'documents',
      label: 'Dokumente',
      icon: 'mdi-file-document-outline',
      value: formatInt(s.documents_total),
      sub: hasTrend
        ? `${trendUp ? '+' : ''}${trendPct.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} % vs. Vormonat`
        : 'Keine Vergleichsdaten',
      trendIcon: hasTrend ? (trendUp ? 'mdi-trending-up' : 'mdi-trending-down') : null,
      trendClass: hasTrend ? (trendUp ? 'is-positive' : 'is-negative') : 'is-muted',
    },
    {
      key: 'this_month',
      label: 'Diesen Monat',
      icon: 'mdi-calendar-outline',
      value: formatInt(s.this_month),
    },
    {
      key: 'correspondents',
      label: 'Korrespondenten',
      icon: 'mdi-account-group-outline',
      value: formatInt(s.correspondents),
      sub: s.correspondents_new > 0 ? `+${formatInt(s.correspondents_new)} neu diesen Monat` : 'Keine neuen',
      trendIcon: s.correspondents_new > 0 ? 'mdi-trending-up' : null,
      trendClass: s.correspondents_new > 0 ? 'is-positive' : 'is-muted',
    },
    {
      key: 'tags',
      label: 'Tags',
      icon: 'mdi-tag-outline',
      value: formatInt(s.tags),
      sub: `${(s.untagged_pct || 0).toLocaleString('de-DE', { maximumFractionDigits: 0 })} % ohne Tags`,
      trendIcon: null,
      trendClass: 'is-muted',
      attentionKey: 'untagged',
    },
    {
      key: 'document_types',
      label: 'Dokumenttypen',
      icon: 'mdi-file-document-multiple-outline',
      value: formatInt(s.document_types ?? overview.value.type_count_total),
      sub: `${withoutDocumentTypePct.toLocaleString('de-DE', { maximumFractionDigits: 0 })} % ohne Dokumenttyp`,
      trendIcon: null,
      trendClass: 'is-muted',
      attentionKey: 'without_document_type',
    },
  ];
});

function handleStatCardClick(card) {
  if (!card?.attentionKey) return;
  emit('attention-select', card.attentionKey);
}

// ── Sparkline (letzte 7 Monate) ─────────────────────────────────────────────
const sparkline = computed(() => {
  const series = overview.value.documents_per_month.slice(-7).map((p) => Number(p.count || 0));
  const max = Math.max(1, ...series);
  return series.map((v) => Math.max(6, Math.round((v / max) * 100)));
});

// ── Jahres-Kombidiagramm (Balken pro Jahr + kumulative Linie) ───────────────
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

// ── Rangliste ───────────────────────────────────────────────────────────────
const topCorrespondents = computed(() => overview.value.top_correspondents || []);
const maxRankCount = computed(() =>
  Math.max(1, ...topCorrespondents.value.map((c) => Number(c.count || 0)))
);
const rankPct = (count) => Math.max(4, Math.round((Number(count || 0) / maxRankCount.value) * 100));
const visibleTopCorrespondents = computed(() =>
  topCorrespondents.value.slice(0, Math.max(1, visibleRankCount.value))
);

function updateVisibleRankCount() {
  const el = rankListEl.value;
  const total = topCorrespondents.value.length;
  if (!el || !total) {
    visibleRankCount.value = 6;
    return;
  }

  const styles = window.getComputedStyle(el);
  const gap = Number.parseFloat(styles.rowGap || styles.gap || '0') || 0;
  const row = el.querySelector('.dash-rank__row');
  const rowHeight = row?.getBoundingClientRect().height || 34;
  const capacity = Math.floor((el.clientHeight + gap) / (rowHeight + gap));
  visibleRankCount.value = Math.max(1, Math.min(total, capacity || 1));
}

function observeRankList(el, oldEl) {
  if (oldEl && rankResizeObserver) rankResizeObserver.unobserve(oldEl);
  if (!el || typeof ResizeObserver === 'undefined') return;
  rankResizeObserver ??= new ResizeObserver(() => updateVisibleRankCount());
  rankResizeObserver.observe(el);
  nextTick(updateVisibleRankCount);
}

watch(rankListEl, observeRankList, { flush: 'post' });
watch(() => topCorrespondents.value.length, () => nextTick(updateVisibleRankCount), { flush: 'post' });

const chartPalette = [
  '#5bb7c8',
  '#7aa2e3',
  '#a78bda',
  '#e8a45d',
  '#75b798',
  '#e27d7d',
  '#94a3b8',
  '#d48ac8',
];

/** Farbpalette fuer Ranglisten, Suchbalken und Donut-Segmente. */
function rampColor(index, total) {
  if (total <= 1) return chartPalette[0];
  return chartPalette[index % chartPalette.length];
}

// ── Verteilung (Donut) – umschaltbar Tags ↔ Dokumenttypen ────────────────────
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

// ── Lückenanalyse: Jahre ohne Dokumente in der Historie ─────────────────────
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

// ── Top-Suchbegriffe ─────────────────────────────────────────────────────────
const topSearches = computed(() => overview.value.top_searches || []);
const maxSearchCount = computed(() =>
  Math.max(1, ...topSearches.value.map((s) => Number(s.count || 0)))
);
const searchPct = (count) => Math.max(6, Math.round((Number(count || 0) / maxSearchCount.value) * 100));

// ── Thumbnails ──────────────────────────────────────────────────────────────
const thumbError = reactive({});
const thumbUrl = (id) => documentThumbnailUrl(id);
</script>

<style scoped>
.dashboard {
  --dash-chart-current: #5bb7c8;
  --dash-chart-line: #7aa2e3;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--pm-content-surface, transparent);
}

.dashboard__scroll {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 26px 30px 30px;
}

/* ── Kopfzeile ─────────────────────────────────────────────────────────── */
.dash-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  flex: none;
}

.dash-head__greeting {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.015em;
  line-height: 1.1;
  color: var(--pm-text);
  margin: 0;
}

.dash-head__meta {
  font-size: 13.5px;
  color: var(--pm-muted);
  margin: 4px 0 0;
}

.dash-head__actions {
  display: flex;
  gap: 9px;
  flex-shrink: 0;
}

.dash-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 36px;
  padding: 0 13px;
  font-size: 13px;
  font-weight: 600;
  border-radius: 9px;
  border: 1px solid var(--pm-divider);
  background: transparent;
  color: var(--pm-muted);
  cursor: pointer;
  transition: background 0.14s ease, color 0.14s ease, border-color 0.14s ease;
}

.dash-btn:hover {
  color: var(--pm-text);
  border-color: color-mix(in srgb, var(--pm-text) 22%, transparent);
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.dash-btn--primary {
  color: var(--pm-accent);
  background: color-mix(in srgb, var(--pm-accent) 13%, transparent);
  border-color: color-mix(in srgb, var(--pm-accent) 32%, transparent);
}

.dash-btn--primary:hover {
  color: var(--pm-accent);
  background: color-mix(in srgb, var(--pm-accent) 20%, transparent);
  border-color: color-mix(in srgb, var(--pm-accent) 45%, transparent);
}

/* ── Karten-Basis ─────────────────────────────────────────────────────── */
.dash-card {
  background: var(--pm-v-card, var(--pm-app-surface-raised));
  border: 1px solid var(--pm-divider);
  border-radius: 16px;
}

/* ── Kennzahlen-Band ──────────────────────────────────────────────────── */
.dash-stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
  flex: none;
}

.dash-stat {
  min-width: 0;
  padding: 16px 17px;
}

.dash-stat--clickable {
  cursor: pointer;
  transition: border-color 0.14s ease, background 0.14s ease;
}

.dash-stat--clickable:hover,
.dash-stat--clickable:focus-visible {
  border-color: color-mix(in srgb, var(--pm-accent) 45%, transparent);
  background: color-mix(in srgb, var(--pm-accent) 5%, var(--pm-v-card, var(--pm-app-surface-raised)));
  outline: none;
}

.dash-stat__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.dash-stat__label {
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--pm-muted);
}

.dash-stat__icon {
  color: color-mix(in srgb, var(--pm-muted) 65%, transparent) !important;
}

.dash-stat__value {
  font-size: 32px;
  font-weight: 650;
  letter-spacing: -0.02em;
  line-height: 1;
  margin-top: 10px;
  color: var(--pm-text);
  font-variant-numeric: tabular-nums;
}

.dash-stat__unit {
  font-size: 15px;
  font-weight: 600;
  color: var(--pm-muted);
  margin-left: 3px;
}

.dash-stat__trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 9px;
  font-size: 12.5px;
  font-weight: 500;
}

.dash-stat__trend.is-positive { color: var(--pm-success); }
.dash-stat__trend.is-negative { color: var(--pm-error); }
.dash-stat__trend.is-muted { color: var(--pm-muted); }

.dash-stat__foot {
  margin-top: 11px;
}

.dash-stat__sub {
  font-size: 12px;
  color: var(--pm-muted);
}

/* Sparkline */
.dash-spark {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 16px;
  margin-top: 12px;
}

.dash-spark__bar {
  flex: 1;
  border-radius: 1px;
  background: color-mix(in srgb, var(--pm-muted) 45%, transparent);
  min-height: 2px;
}

.dash-spark__bar--current {
  background: var(--dash-chart-current);
}

/* ── Visualisierungen ─────────────────────────────────────────────────── */
.dash-viz {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
  flex: 0 1 clamp(330px, 45vh, 460px);
  min-height: 0;
}

.dash-chart {
  grid-column: 1 / span 3;
}

.dash-viz__side {
  grid-column: 4 / span 2;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.dash-chart,
.dash-rank,
.dash-donut-card {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.dash-card__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--pm-text);
  margin: 0;
}

.dash-card__subtitle {
  font-size: 12.5px;
  color: var(--pm-muted);
  margin: 3px 0 0;
}

.dash-card__empty {
  font-size: 13px;
  color: var(--pm-muted);
  margin: 14px 0 2px;
}

/* Balkendiagramm */
.dash-chart {
  padding: 18px 20px 16px;
  display: flex;
  flex-direction: column;
}

.dash-chart__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.dash-chart__total {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--pm-muted);
  white-space: nowrap;
}

.dash-chart__legend {
  display: flex;
  gap: 14px;
  margin-top: 8px;
}

.dash-chart__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--pm-muted);
}

.dash-chart__legend-swatch--bar {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  background: color-mix(in srgb, var(--pm-muted) 40%, transparent);
}

.dash-chart__legend-swatch--line {
  width: 16px;
  height: 2px;
  border-radius: 2px;
  background: var(--dash-chart-line);
}

.dash-chart__gap {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: var(--pm-warning);
}

.dash-bars__bar--gap {
  background: repeating-linear-gradient(
    45deg,
    color-mix(in srgb, var(--pm-warning) 32%, transparent) 0 2px,
    transparent 2px 4px
  );
  min-height: 4px;
  border-radius: 2px 2px 0 0;
}

.dash-chart__plot {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
}

.dash-bars {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  border-bottom: 1px solid var(--pm-divider);
}

.dash-line {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
  animation: dash-line-reveal 0.72s ease-out 0.12s both;
}

.dash-line__path {
  fill: none;
  stroke: var(--dash-chart-line);
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
  opacity: 0.9;
}

.dash-line__dot {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dash-chart-line);
  transform: translate(-50%, -50%);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--dash-chart-line) 22%, transparent);
  pointer-events: none;
  opacity: 0;
  animation: dash-dot-pop 0.28s ease-out 0.74s forwards;
}

.dash-bars__col {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: flex-end;
}

.dash-bars__bar {
  width: 100%;
  padding: 0;
  border: 0;
  border-radius: 4px 4px 0 0;
  background: color-mix(in srgb, var(--pm-muted) 34%, transparent);
  transition: background 0.14s ease, transform 0.14s ease;
  min-height: 2px;
  transform-origin: bottom;
  animation: dash-bar-grow 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) both;
  cursor: pointer;
}

.dash-bars__col:nth-child(2) .dash-bars__bar { animation-delay: 0.03s; }
.dash-bars__col:nth-child(3) .dash-bars__bar { animation-delay: 0.06s; }
.dash-bars__col:nth-child(4) .dash-bars__bar { animation-delay: 0.09s; }
.dash-bars__col:nth-child(5) .dash-bars__bar { animation-delay: 0.12s; }
.dash-bars__col:nth-child(6) .dash-bars__bar { animation-delay: 0.15s; }
.dash-bars__col:nth-child(7) .dash-bars__bar { animation-delay: 0.18s; }
.dash-bars__col:nth-child(8) .dash-bars__bar { animation-delay: 0.21s; }
.dash-bars__col:nth-child(9) .dash-bars__bar { animation-delay: 0.24s; }
.dash-bars__col:nth-child(10) .dash-bars__bar { animation-delay: 0.27s; }
.dash-bars__col:nth-child(11) .dash-bars__bar { animation-delay: 0.3s; }
.dash-bars__col:nth-child(12) .dash-bars__bar { animation-delay: 0.33s; }

.dash-bars__bar:hover {
  background: color-mix(in srgb, var(--pm-muted) 52%, transparent);
  transform: scaleY(1.015);
}

.dash-bars__bar:focus-visible {
  outline: 2px solid var(--dash-chart-line);
  outline-offset: 3px;
}

.dash-bars__bar--current {
  background: var(--dash-chart-current);
}

.dash-bars__axis {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.dash-bars__tick {
  flex: 1;
  text-align: center;
  font-size: 11px;
  color: var(--pm-muted);
}

.dash-bars__tick--current {
  font-weight: 600;
  color: var(--pm-accent);
}

/* Rangliste */
.dash-rank {
  flex: 1 1 auto;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
}

.dash-rank__list {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  gap: 10px;
  margin-top: 16px;
  min-height: 0;
  overflow: hidden;
}

.dash-rank__row {
  flex: none;
}

.dash-rank__meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 5px;
}

.dash-rank__name {
  font-size: 13px;
  color: color-mix(in srgb, var(--pm-text) 88%, transparent);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dash-rank__count {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--pm-muted);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.dash-rank__track {
  height: 6px;
  border-radius: 3px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  overflow: hidden;
}

.dash-rank__fill {
  display: block;
  height: 100%;
  border-radius: 3px;
  transform-origin: left center;
  animation: dash-fill-grow 0.5s ease-out both;
}

.dash-rank__row:nth-child(2) .dash-rank__fill { animation-delay: 0.05s; }
.dash-rank__row:nth-child(3) .dash-rank__fill { animation-delay: 0.1s; }
.dash-rank__row:nth-child(4) .dash-rank__fill { animation-delay: 0.15s; }
.dash-rank__row:nth-child(5) .dash-rank__fill { animation-delay: 0.2s; }

/* Donut */
.dash-donut-card {
  padding: 18px 20px;
}

.dash-donut-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.dash-toggle {
  display: inline-flex;
  padding: 2px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.06);
}

.dash-toggle__btn {
  padding: 3px 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-muted);
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.14s ease, color 0.14s ease;
}

.dash-toggle__btn--active {
  background: var(--pm-v-card, var(--pm-app-surface-raised));
  color: var(--pm-accent);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

.dash-donut-card__body {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-top: 14px;
}

.dash-donut {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  flex-shrink: 0;
  animation: dash-donut-in 0.5s ease-out both;
}

/* Farbfläche als eigene Ebene, damit die Uhrzeiger-Maske das Mittelloch
   (den Zählwert) nicht miterfasst. */
.dash-donut::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: var(--dash-donut-gradient, var(--pm-divider));
  -webkit-mask: conic-gradient(from 0deg, #000 var(--dash-donut-sweep, 360deg), transparent 0);
  mask: conic-gradient(from 0deg, #000 var(--dash-donut-sweep, 360deg), transparent 0);
  animation: dash-donut-sweep 0.7s cubic-bezier(0.2, 0.8, 0.2, 1) both;
}

.dash-donut__hole {
  position: absolute;
  inset: 18px;
  border-radius: 50%;
  background: var(--pm-v-card, var(--pm-app-surface-raised));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.dash-donut__value {
  font-size: 17px;
  font-weight: 650;
  color: var(--pm-text);
  line-height: 1;
}

.dash-donut__label {
  font-size: 10px;
  color: var(--pm-muted);
  margin-top: 2px;
}

.dash-legend {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}

.dash-legend__item {
  display: flex;
  align-items: center;
  gap: 8px;
  animation: dash-fade-up 0.34s ease-out both;
}

.dash-legend__item:nth-child(2) { animation-delay: 0.05s; }
.dash-legend__item:nth-child(3) { animation-delay: 0.1s; }
.dash-legend__item:nth-child(4) { animation-delay: 0.15s; }
.dash-legend__item:nth-child(5) { animation-delay: 0.2s; }
.dash-legend__item:nth-child(6) { animation-delay: 0.25s; }

.dash-legend__swatch {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  flex-shrink: 0;
}

.dash-legend__name {
  font-size: 12.5px;
  color: color-mix(in srgb, var(--pm-text) 85%, transparent);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.dash-legend__count {
  font-size: 12px;
  font-weight: 600;
  color: var(--pm-muted);
  font-variant-numeric: tabular-nums;
}

/* ── Untere Inhalte ──────────────────────────────────────────────────── */
.dash-lower {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
}

.dash-lower__main {
  grid-column: 1 / span 3;
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(220px, 1fr);
  grid-template-rows: minmax(0, 1fr);
  align-items: stretch;
  gap: 14px;
  min-width: 0;
  min-height: 0;
}

.dash-lower__side {
  grid-column: 4 / span 2;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.dash-lower__side .dash-donut-card {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
}

.dash-lower__side .dash-donut-card__body {
  flex: 1 1 auto;
  align-items: center;
  justify-content: center;
  min-height: 0;
  overflow: hidden;
}

.dash-lower__side .dash-donut {
  width: clamp(128px, min(17vw, 29vh), 200px);
  height: clamp(128px, min(17vw, 29vh), 200px);
}

.dash-lower__side .dash-donut__hole {
  inset: clamp(24px, min(3.4vw, 5.8vh), 40px);
}

.dash-lower__side .dash-donut__value {
  font-size: clamp(22px, 2.4vw, 34px);
}

.dash-lower__side .dash-donut__label {
  font-size: clamp(11px, 1.1vw, 15px);
}

.dash-recent {
  min-width: 0;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.dash-searches {
  min-width: 0;
  min-height: 128px;
  height: 100%;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dash-searches .dash-card__title {
  margin-bottom: 12px;
}

.dash-searches__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
  overflow: hidden;
}

.dash-searches__row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dash-searches__term {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  padding: 0;
  border: 0;
  background: none;
  cursor: pointer;
  text-align: left;
}

.dash-searches__icon {
  flex: none;
  color: var(--pm-muted) !important;
}

.dash-searches__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12.5px;
  color: color-mix(in srgb, var(--pm-text) 88%, transparent);
}

.dash-searches__term:hover .dash-searches__label {
  color: var(--pm-accent);
}

.dash-searches__count {
  flex: none;
  font-size: 12px;
  font-weight: 600;
  color: var(--pm-muted);
  font-variant-numeric: tabular-nums;
}

.dash-searches__track {
  height: 5px;
  border-radius: 3px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  overflow: hidden;
}

.dash-searches__fill {
  display: block;
  height: 100%;
  border-radius: 3px;
  transform-origin: left center;
  animation: dash-fill-grow 0.46s ease-out both;
}

.dash-searches__row:nth-child(2) .dash-searches__fill { animation-delay: 0.05s; }
.dash-searches__row:nth-child(3) .dash-searches__fill { animation-delay: 0.1s; }
.dash-searches__row:nth-child(4) .dash-searches__fill { animation-delay: 0.15s; }

.dash-recent__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.dash-link {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--pm-accent);
  background: none;
  border: 0;
  cursor: pointer;
  padding: 0;
}

.dash-link:hover { text-decoration: underline; }

.dash-recent__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  gap: 14px;
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.dash-doc {
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding: 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.14s ease;
  width: 100%;
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.dash-doc:hover {
  border-color: color-mix(in srgb, var(--pm-text) 20%, transparent);
}

.dash-doc__thumb {
  width: clamp(56px, 18%, 92px);
  height: min(72%, 128px);
  border-radius: 6px;
  flex-shrink: 0;
  align-self: center;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--v-theme-on-surface), 0.05);
  border: 1px solid var(--pm-divider);
  color: var(--pm-muted);
}

.dash-doc__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dash-doc__text {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  flex: 1;
}

.dash-doc__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--pm-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dash-doc__corr {
  font-size: 12px;
  color: var(--pm-muted);
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dash-doc__date {
  font-size: 11.5px;
  color: color-mix(in srgb, var(--pm-muted) 80%, transparent);
  margin-top: 2px;
}

/* ── Leerer Zustand ───────────────────────────────────────────────────── */
.dash-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 64px 20px;
  color: var(--pm-muted);
}

.dash-empty__icon {
  color: color-mix(in srgb, var(--pm-accent) 70%, var(--pm-muted));
  margin-bottom: 14px;
}

.dash-empty__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--pm-text);
  margin: 0 0 6px;
}

.dash-empty__text {
  font-size: 13.5px;
  max-width: 360px;
  margin: 0 0 18px;
}

.dash-empty__cta { height: 40px; }

/* ── Skeleton ─────────────────────────────────────────────────────────── */
.dash-stats.is-loading .dash-stat__value,
.dash-stats.is-loading .dash-stat__trend {
  opacity: 0.35;
}

/* ── Diagramm-Animationen ─────────────────────────────────────────────── */
@keyframes dash-bar-grow {
  from {
    opacity: 0.55;
    transform: scaleY(0.08);
  }
  to {
    opacity: 1;
    transform: scaleY(1);
  }
}

@keyframes dash-fill-grow {
  from {
    opacity: 0.45;
    transform: scaleX(0);
  }
  to {
    opacity: 1;
    transform: scaleX(1);
  }
}

@keyframes dash-line-reveal {
  from { clip-path: inset(0 100% 0 0); }
  to { clip-path: inset(0 0 0 0); }
}

@keyframes dash-dot-pop {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.55);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
}

@keyframes dash-donut-in {
  from {
    opacity: 0;
    transform: scale(0.92) rotate(-8deg);
  }
  to {
    opacity: 1;
    transform: scale(1) rotate(0deg);
  }
}

@keyframes dash-donut-sweep {
  from {
    --dash-donut-sweep: 0deg;
  }
  to {
    --dash-donut-sweep: 360deg;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dash-donut,
  .dash-donut::before {
    animation: none;
  }
  .dash-donut::before {
    --dash-donut-sweep: 360deg;
  }
}

@keyframes dash-fade-up {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .dash-bars__bar,
  .dash-rank__fill,
  .dash-searches__fill,
  .dash-donut,
  .dash-legend__item,
  .dash-line {
    animation: none;
    opacity: 1;
    transform: none;
  }

  .dash-line__dot {
    animation: none;
    opacity: 1;
    transform: translate(-50%, -50%);
  }
}

/* ── Responsive ───────────────────────────────────────────────────────── */
@media (max-height: 920px) and (min-width: 1181px) {
  .dashboard__scroll {
    padding: 18px 24px 20px;
  }

  .dash-head {
    margin-bottom: 12px;
  }

  .dash-head__greeting {
    font-size: 19px;
  }

  .dash-head__meta {
    font-size: 12.5px;
  }

  .dash-btn {
    height: 32px;
    padding: 0 11px;
  }

  .dash-stats {
    gap: 12px;
    margin-bottom: 12px;
  }

  .dash-stat {
    padding: 12px 14px;
  }

  .dash-stat__value {
    font-size: 26px;
    margin-top: 7px;
  }

  .dash-stat__trend {
    margin-top: 6px;
    font-size: 11.5px;
  }

  .dash-spark {
    height: 12px;
    margin-top: 9px;
  }

  .dash-viz {
    gap: 12px;
    margin-bottom: 12px;
    flex-basis: clamp(300px, 42vh, 390px);
    min-height: 250px;
  }

  .dash-chart,
  .dash-rank,
  .dash-donut-card {
    padding: 14px 16px;
  }

  .dash-chart__head {
    margin-bottom: 10px;
  }

  .dash-chart__plot {
    min-height: 150px;
  }

  .dash-rank__list {
    gap: 9px;
    margin-top: 12px;
  }

  .dash-lower {
    gap: 12px;
    flex: 1 1 0;
    min-height: 0;
  }

  .dash-lower__main {
    gap: 12px;
  }

  .dash-searches {
    min-height: 0;
    padding: 12px 14px;
  }

  .dash-recent__head {
    margin-bottom: 8px;
  }

  .dash-recent__grid {
    grid-template-rows: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .dash-doc {
    min-height: 0;
    gap: 10px;
    padding: 9px 10px;
    overflow: hidden;
  }

  .dash-doc__thumb {
    width: clamp(48px, 17%, 76px);
    height: min(70%, 104px);
  }

  .dash-doc__title {
    font-size: 12.5px;
  }

  .dash-doc__corr {
    font-size: 11.5px;
    margin-top: 2px;
  }

  .dash-doc__date {
    font-size: 11px;
    margin-top: 1px;
  }

  .dash-lower__side .dash-donut {
    width: clamp(118px, min(15vw, 26vh), 170px);
    height: clamp(118px, min(15vw, 26vh), 170px);
  }

  .dash-lower__side .dash-donut__hole {
    inset: clamp(22px, min(3vw, 5vh), 34px);
  }
}

@media (max-height: 700px) and (min-width: 1181px) {
  .dashboard__scroll {
    padding: 14px 20px 16px;
  }

  .dash-head {
    margin-bottom: 9px;
  }

  .dash-head__meta {
    display: none;
  }

  .dash-stats {
    margin-bottom: 10px;
  }

  .dash-stat {
    padding: 10px 12px;
  }

  .dash-stat__value {
    font-size: 23px;
  }

  .dash-stat__trend {
    font-size: 11px;
  }

  .dash-viz {
    flex-basis: clamp(230px, 34vh, 280px);
    min-height: 210px;
    margin-bottom: 10px;
  }

  .dash-chart__legend {
    margin-top: 5px;
  }

  .dash-chart__plot {
    min-height: 112px;
  }

  .dash-lower {
    flex: 1 1 0;
    min-height: 0;
  }

  .dash-recent__grid {
    grid-template-rows: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .dash-doc {
    min-height: 0;
    padding: 8px 9px;
  }

  .dash-doc__thumb {
    display: none;
  }

  .dash-doc__title {
    font-size: 12px;
  }

  .dash-doc__corr {
    font-size: 11px;
  }

  .dash-doc__date {
    display: none;
  }

  .dash-searches .dash-card__title {
    margin-bottom: 9px;
  }
}

@media (max-height: 620px) and (min-width: 1181px) {
  .dashboard__scroll {
    padding: 10px 18px 12px;
  }

  .dash-head__actions {
    gap: 6px;
  }

  .dash-btn {
    height: 28px;
    padding: 0 9px;
    font-size: 12px;
  }

  .dash-stats {
    margin-bottom: 8px;
  }

  .dash-stat {
    padding: 8px 10px;
  }

  .dash-stat__label {
    font-size: 10.5px;
  }

  .dash-stat__value {
    font-size: 20px;
  }

  .dash-stat__trend {
    margin-top: 4px;
  }

  .dash-viz {
    flex-basis: clamp(180px, 30vh, 220px);
    min-height: 170px;
    margin-bottom: 8px;
  }

  .dash-chart,
  .dash-rank,
  .dash-donut-card {
    padding: 10px 12px;
  }

  .dash-card__title {
    font-size: 13.5px;
  }

  .dash-card__subtitle,
  .dash-chart__legend,
  .dash-chart__total {
    font-size: 11px;
  }

  .dash-chart__plot {
    min-height: 82px;
  }

  .dash-rank__list {
    gap: 6px;
    margin-top: 8px;
  }

  .dash-rank__track {
    height: 4px;
  }

  .dash-recent__head {
    margin-bottom: 6px;
  }

  .dash-recent__grid {
    gap: 6px;
  }

  .dash-doc {
    align-items: stretch;
    padding: 5px 8px;
    border-radius: 10px;
  }

  .dash-doc__corr {
    display: none;
  }

  .dash-searches {
    padding: 10px 12px;
  }

  .dash-searches__list {
    gap: 6px;
  }

  .dash-lower__side .dash-donut {
    width: 96px;
    height: 96px;
  }

  .dash-lower__side .dash-donut__hole {
    inset: 20px;
  }
}

@media (max-width: 1180px) {
  .dash-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .dash-viz {
    grid-template-columns: minmax(0, 1fr);
    min-height: 0;
    flex-basis: auto;
  }
  .dash-chart__plot { min-height: 240px; }
  .dash-chart,
  .dash-viz__side {
    grid-column: auto;
  }
  .dash-lower { grid-template-columns: minmax(0, 1fr); }
  .dash-lower__main,
  .dash-lower__side,
  .dash-searches {
    grid-column: auto;
  }
  .dash-lower__side .dash-donut {
    width: 128px;
    height: 128px;
  }
  .dash-lower__side .dash-donut__hole { inset: 24px; }
  .dash-lower__side .dash-donut__value { font-size: 22px; }
  .dash-lower__side .dash-donut__label { font-size: 11px; }
  .dash-searches { min-height: 128px; }
}

@media (max-width: 720px) {
  .dashboard__scroll { padding: 18px 16px 24px; }
  .dash-head { flex-direction: column; align-items: stretch; }
  .dash-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dash-lower__main { grid-template-columns: minmax(0, 1fr); }
  .dash-recent__grid {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: none;
  }
}
</style>
