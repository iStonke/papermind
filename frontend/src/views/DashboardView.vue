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
          <button type="button" class="dash-btn" @click="emit('open-scan')">
            <v-icon size="15">mdi-scanner</v-icon>
            Scannen
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
          <article v-for="card in statCards" :key="card.key" class="dash-card dash-stat">
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
            <div v-else-if="card.key === 'storage'" class="dash-stat__foot">
              <div v-if="storagePct !== null" class="dash-progress">
                <span class="dash-progress__fill" :style="{ width: `${storagePct}%` }" />
              </div>
              <span class="dash-stat__sub">{{ card.sub }}</span>
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
                </div>
              </div>
              <span class="dash-chart__total">{{ formatInt(cumulativeTotal) }} gesamt</span>
            </div>

            <div v-if="years.length" class="dash-chart__plot">
              <div class="dash-bars">
                <div v-for="(p, i) in years" :key="p.year" class="dash-bars__col">
                  <div
                    class="dash-bars__bar"
                    :class="{ 'dash-bars__bar--current': i === years.length - 1 }"
                    :style="{ height: `${yearBarHeight(p.count)}%` }"
                    :title="`${p.year}: ${p.count} Dokumente`"
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
              <div v-if="overview.top_correspondents.length" class="dash-rank__list">
                <div v-for="(c, i) in overview.top_correspondents" :key="c.name" class="dash-rank__row">
                  <div class="dash-rank__meta">
                    <span class="dash-rank__name">{{ c.name }}</span>
                    <span class="dash-rank__count">{{ formatInt(c.count) }}</span>
                  </div>
                  <div class="dash-rank__track">
                    <span
                      class="dash-rank__fill"
                      :style="{ width: `${rankPct(c.count)}%`, background: rampColor(i, overview.top_correspondents.length) }"
                    />
                  </div>
                </div>
              </div>
              <p v-else class="dash-card__empty">Noch keine Korrespondenten zugeordnet.</p>
            </article>

            <!-- Tag-Verteilung -->
            <article class="dash-card dash-donut-card">
              <h2 class="dash-card__title">Tag-Verteilung</h2>
              <div v-if="overview.tag_distribution.length" class="dash-donut-card__body">
                <div class="dash-donut" :style="{ background: donutGradient }">
                  <div class="dash-donut__hole">
                    <span class="dash-donut__value">{{ formatInt(overview.tag_count_total) }}</span>
                    <span class="dash-donut__label">Tags</span>
                  </div>
                </div>
                <ul class="dash-legend">
                  <li v-for="(t, i) in legendTags" :key="t.tag" class="dash-legend__item">
                    <span class="dash-legend__swatch" :style="{ background: rampColor(i, legendTags.length) }" />
                    <span class="dash-legend__name">{{ t.tag }}</span>
                    <span class="dash-legend__count">{{ formatInt(t.count) }}</span>
                  </li>
                </ul>
              </div>
              <p v-else class="dash-card__empty">Noch keine Tags vergeben.</p>
            </article>
          </div>
        </div>

        <!-- 4) Aufmerksamkeit -->
        <div class="dash-attention">
          <button
            v-for="tile in attentionTiles"
            :key="tile.key"
            type="button"
            class="dash-card dash-tile"
            :class="`dash-tile--${tile.tone}`"
            @click="emit('attention-select', tile.key)"
          >
            <span class="dash-tile__badge">
              <v-icon size="18">{{ tile.icon }}</v-icon>
            </span>
            <span class="dash-tile__body">
              <span class="dash-tile__value">{{ formatInt(tile.value) }}</span>
              <span class="dash-tile__label">{{ tile.label }}</span>
            </span>
            <v-icon size="16" class="dash-tile__chevron">mdi-chevron-right</v-icon>
          </button>
        </div>

        <!-- 5) Zuletzt -->
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
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../stores/dashboard.js';
import { documentThumbnailUrl } from '../api/documents.js';

const emit = defineEmits([
  'open-import',
  'open-scan',
  'open-ai',
  'open-document',
  'attention-select',
  'show-all-recent',
]);

const dashboardStore = useDashboardStore();
const { overview, isLoading, hasLoadedOnce } = storeToRefs(dashboardStore);

onMounted(() => {
  void dashboardStore.fetchOverview();
});

const showSkeleton = computed(() => isLoading.value && !hasLoadedOnce.value);
const isEmpty = computed(() => hasLoadedOnce.value && overview.value.stats.documents_total === 0);

// ── Formatierung ────────────────────────────────────────────────────────────
const intFormatter = new Intl.NumberFormat('de-DE');
const formatInt = (n) => intFormatter.format(Number(n || 0));

function formatStorage(bytes) {
  const b = Number(bytes || 0);
  if (b < 1024) return { value: String(b), unit: ' B' };
  const units = [' KB', ' MB', ' GB', ' TB'];
  let val = b / 1024;
  let idx = 0;
  while (val >= 1024 && idx < units.length - 1) { val /= 1024; idx += 1; }
  const digits = val >= 100 ? 0 : 1;
  return { value: val.toLocaleString('de-DE', { minimumFractionDigits: digits, maximumFractionDigits: digits }), unit: units[idx] };
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// ── Kopfzeile ───────────────────────────────────────────────────────────────
const greeting = computed(() => {
  const h = new Date().getHours();
  const part = h < 5 ? 'Gute Nacht' : h < 11 ? 'Guten Morgen' : h < 18 ? 'Guten Tag' : 'Guten Abend';
  return part;
});

const headMeta = computed(() =>
  new Date().toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
);

// ── Kennzahlen-Karten ───────────────────────────────────────────────────────
const statCards = computed(() => {
  const s = overview.value.stats;
  const storage = formatStorage(s.storage_bytes);
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
    },
    {
      key: 'storage',
      label: 'Speicher',
      icon: 'mdi-database-outline',
      value: storage.value,
      unit: storage.unit,
      sub: s.storage_limit_bytes
        ? `von ${formatStorage(s.storage_limit_bytes).value}${formatStorage(s.storage_limit_bytes).unit}`
        : 'belegt',
    },
  ];
});

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
const maxRankCount = computed(() =>
  Math.max(1, ...overview.value.top_correspondents.map((c) => Number(c.count || 0)))
);
const rankPct = (count) => Math.max(4, Math.round((Number(count || 0) / maxRankCount.value) * 100));

/** Teal→Slate-Rampe, theme-adaptiv über vorhandene Tokens. */
function rampColor(index, total) {
  if (total <= 1) return 'var(--pm-accent)';
  const t = index / (total - 1); // 0 = stärkster
  const accentShare = Math.round((1 - t) * 78 + 12); // 90%…12%
  return `color-mix(in srgb, var(--pm-accent) ${accentShare}%, var(--pm-muted))`;
}

// ── Donut ───────────────────────────────────────────────────────────────────
const legendTags = computed(() => overview.value.tag_distribution.slice(0, 4));

const donutGradient = computed(() => {
  const tags = overview.value.tag_distribution;
  const total = tags.reduce((sum, t) => sum + Number(t.count || 0), 0);
  if (total <= 0) return 'var(--pm-divider)';
  let acc = 0;
  const stops = tags.map((t, i) => {
    const start = (acc / total) * 360;
    acc += Number(t.count || 0);
    const end = (acc / total) * 360;
    return `${rampColor(i, tags.length)} ${start}deg ${end}deg`;
  });
  return `conic-gradient(${stops.join(', ')})`;
});

// ── Aufmerksamkeit ──────────────────────────────────────────────────────────
const attentionTiles = computed(() => {
  const a = overview.value.attention;
  return [
    { key: 'unread', label: 'Ungelesen', value: a.unread, icon: 'mdi-information-outline', tone: 'teal' },
    { key: 'untagged', label: 'Ohne Tags', value: a.untagged, icon: 'mdi-tag-off-outline', tone: 'neutral' },
    { key: 'retention_due', label: 'Fristen laufen ab', value: a.retention_due, icon: 'mdi-clock-outline', tone: 'amber' },
    { key: 'to_review', label: 'Zu prüfen', value: a.to_review, icon: 'mdi-alert-outline', tone: 'amber' },
  ];
});

// ── Speicher-Progress ───────────────────────────────────────────────────────
const storagePct = computed(() => {
  const s = overview.value.stats;
  if (!s.storage_limit_bytes) return null;
  return Math.min(100, Math.round((Number(s.storage_bytes || 0) / Number(s.storage_limit_bytes)) * 100));
});

// ── Thumbnails ──────────────────────────────────────────────────────────────
const thumbError = reactive({});
const thumbUrl = (id) => documentThumbnailUrl(id);
</script>

<style scoped>
.dashboard {
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
  background: var(--pm-accent);
}

/* Progress */
.dash-progress {
  height: 5px;
  border-radius: 3px;
  background: rgba(var(--v-theme-on-surface), 0.1);
  overflow: hidden;
  margin-bottom: 5px;
}

.dash-progress__fill {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: var(--pm-accent);
}

/* ── Visualisierungen ─────────────────────────────────────────────────── */
.dash-viz {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(0, 1fr);
  gap: 16px;
  margin-bottom: 16px;
  flex: 1 1 auto;
  min-height: 0;
}

.dash-viz__side {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
  background: var(--pm-accent);
}

.dash-chart__plot {
  position: relative;
  flex: 1 1 auto;
  min-height: 90px;
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
}

.dash-line__path {
  fill: none;
  stroke: var(--pm-accent);
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
  background: var(--pm-accent);
  transform: translate(-50%, -50%);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--pm-accent) 22%, transparent);
  pointer-events: none;
}

.dash-bars__col {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: flex-end;
}

.dash-bars__bar {
  width: 100%;
  border-radius: 4px 4px 0 0;
  background: color-mix(in srgb, var(--pm-muted) 34%, transparent);
  transition: background 0.14s ease;
  min-height: 2px;
}

.dash-bars__bar:hover {
  background: color-mix(in srgb, var(--pm-muted) 52%, transparent);
}

.dash-bars__bar--current {
  background: var(--pm-accent);
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
  padding: 18px 20px;
}

.dash-rank__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
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
}

/* Donut */
.dash-donut-card {
  padding: 18px 20px;
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
}

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

/* ── Aufmerksamkeit ───────────────────────────────────────────────────── */
.dash-attention {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
  flex: none;
}

.dash-tile {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 13px;
  padding: 14px 16px;
  border-radius: 14px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.14s ease, background 0.14s ease;
}

.dash-tile:hover {
  background: rgba(var(--v-theme-on-surface), 0.02);
}

.dash-tile__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  flex-shrink: 0;
}

.dash-tile__body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.dash-tile__value {
  font-size: 20px;
  font-weight: 650;
  line-height: 1;
  color: var(--pm-text);
  font-variant-numeric: tabular-nums;
}

.dash-tile__label {
  font-size: 12.5px;
  color: var(--pm-muted);
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dash-tile__chevron {
  color: color-mix(in srgb, var(--pm-muted) 70%, transparent) !important;
  flex-shrink: 0;
}

.dash-tile--teal .dash-tile__badge {
  background: color-mix(in srgb, var(--pm-accent) 14%, transparent);
  color: var(--pm-accent);
}
.dash-tile--teal:hover { border-color: color-mix(in srgb, var(--pm-accent) 45%, transparent); }

.dash-tile--neutral .dash-tile__badge {
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: var(--pm-muted);
}
.dash-tile--neutral:hover { border-color: color-mix(in srgb, var(--pm-accent) 45%, transparent); }

.dash-tile--amber .dash-tile__badge {
  background: color-mix(in srgb, var(--pm-warning) 16%, transparent);
  color: var(--pm-warning);
}
.dash-tile--amber:hover { border-color: color-mix(in srgb, var(--pm-warning) 50%, transparent); }

/* ── Zuletzt ──────────────────────────────────────────────────────────── */
.dash-recent {
  flex: none;
}

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
  display: flex;
  gap: 14px;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 6px;
  scroll-snap-type: x proximity;
  scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--pm-muted) 45%, transparent) transparent;
}

.dash-recent__grid::-webkit-scrollbar {
  height: 8px;
}

.dash-recent__grid::-webkit-scrollbar-thumb {
  background: color-mix(in srgb, var(--pm-muted) 40%, transparent);
  border-radius: 4px;
}

.dash-recent__grid::-webkit-scrollbar-track {
  background: transparent;
}

.dash-doc {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.14s ease;
  /* Fixe Grundbreite: füllt bei wenigen Karten die Reihe (grow),
     scrollt bei vielen/langen Titeln horizontal statt herauszuragen. */
  flex: 1 0 240px;
  min-width: 0;
  scroll-snap-align: start;
}

.dash-doc:hover {
  border-color: color-mix(in srgb, var(--pm-text) 20%, transparent);
}

.dash-doc__thumb {
  width: 42px;
  height: 54px;
  border-radius: 6px;
  flex-shrink: 0;
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

/* ── Responsive ───────────────────────────────────────────────────────── */
@media (max-width: 1180px) {
  .dash-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .dash-viz { grid-template-columns: minmax(0, 1fr); }
  .dash-attention { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 720px) {
  .dashboard__scroll { padding: 18px 16px 24px; }
  .dash-head { flex-direction: column; align-items: stretch; }
  .dash-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dash-attention { grid-template-columns: minmax(0, 1fr); }
}
</style>
