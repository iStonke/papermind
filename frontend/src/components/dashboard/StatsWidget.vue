<!--
  StatsWidget — Kennzahlen-Band (Dokumente, Diesen Monat, Korrespondenten, Tags,
  Dokumenttypen) mit Sparkline und Trend. Klickbare Karten (Tags/Dokumenttypen)
  melden über die Host-Aktion attentionSelect zurück.
-->
<template>
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
</template>

<script setup>
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../../stores/dashboard.js';
import { formatInt, useDashboardActions } from './dashboardShared.js';
import './dashboard.css';

const dashboardStore = useDashboardStore();
const { overview, isLoading, hasLoadedOnce } = storeToRefs(dashboardStore);
const actions = useDashboardActions();

const showSkeleton = computed(() => isLoading.value && !hasLoadedOnce.value);

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
  actions.attentionSelect(card.attentionKey);
}

// Sparkline (letzte 7 Monate)
const sparkline = computed(() => {
  const series = overview.value.documents_per_month.slice(-7).map((p) => Number(p.count || 0));
  const max = Math.max(1, ...series);
  return series.map((v) => Math.max(6, Math.round((v / max) * 100)));
});
</script>
