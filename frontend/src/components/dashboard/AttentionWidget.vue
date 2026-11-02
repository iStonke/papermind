<!--
  AttentionWidget — handlungsleitende Kacheln (Ungelesen, Nicht klassifiziert,
  OCR prüfen, Fristen laufen ab). Klick öffnet über die Host-Aktion
  attentionSelect die serverseitig gefilterte Liste (Query-Param `attention`).
  Kacheln ohne Treffer sind nicht klickbar und zeigen „Alles erledigt".
-->
<template>
  <div class="dash-stats dash-attention" :class="{ 'is-loading': showSkeleton }">
    <article
      v-for="card in attentionCards"
      :key="card.key"
      class="dash-card dash-stat"
      :class="{ 'dash-stat--clickable': card.clickable }"
      :role="card.clickable ? 'button' : undefined"
      :tabindex="card.clickable ? 0 : undefined"
      :aria-label="card.clickable ? `${card.label}: ${card.value} Dokumente anzeigen` : undefined"
      @click="handleCardClick(card)"
      @keydown.enter.prevent="handleCardClick(card)"
      @keydown.space.prevent="handleCardClick(card)"
    >
      <div class="dash-stat__head">
        <span class="dash-stat__label">{{ card.label }}</span>
        <v-icon size="16" class="dash-stat__icon">{{ card.icon }}</v-icon>
      </div>
      <div class="dash-stat__value">{{ card.value }}</div>
      <div class="dash-stat__trend" :class="card.clickable ? 'is-muted' : 'is-positive'">
        <v-icon v-if="!card.clickable" size="13">mdi-check-circle-outline</v-icon>
        {{ card.clickable ? card.sub : 'Alles erledigt' }}
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

// Reihenfolge = Kachelreihenfolge; Keys entsprechen DocumentAttentionFilter.
const ATTENTION_CARDS = [
  { key: 'unread', label: 'Ungelesen', icon: 'mdi-email-outline', sub: 'Noch nicht geöffnet' },
  { key: 'unclassified', label: 'Nicht klassifiziert', icon: 'mdi-robot-outline', sub: 'KI-Analyse offen oder fehlgeschlagen' },
  { key: 'ocr_issues', label: 'OCR prüfen', icon: 'mdi-text-recognition', sub: 'Ohne Text oder unsichere Erkennung' },
  { key: 'retention_due', label: 'Fristen laufen ab', icon: 'mdi-calendar-clock', sub: 'Aufbewahrung endet in 30 Tagen' },
];

const attentionCards = computed(() => {
  const attention = overview.value.attention || {};
  return ATTENTION_CARDS.map((card) => {
    const count = Math.max(0, Number(attention[card.key] || 0));
    return { ...card, value: formatInt(count), clickable: count > 0 };
  });
});

function handleCardClick(card) {
  if (!card?.clickable) return;
  actions.attentionSelect(card.key);
}
</script>
