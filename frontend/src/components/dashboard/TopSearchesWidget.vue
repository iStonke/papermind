<!--
  TopSearchesWidget — häufigste Suchbegriffe des Owners. Klick auf einen Begriff
  löst die Suche über die Host-Aktion searchTerm aus.
-->
<template>
  <article class="dash-card dash-searches">
    <h2 class="dash-card__title">Häufig gesucht</h2>
    <ul v-if="topSearches.length" class="dash-searches__list">
      <li v-for="(s, i) in topSearches" :key="s.term" class="dash-searches__row">
        <button type="button" class="dash-searches__term" :title="s.term" @click="actions.searchTerm(s.term)">
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
</template>

<script setup>
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../../stores/dashboard.js';
import { formatInt, rampColor, useDashboardActions } from './dashboardShared.js';
import './dashboard.css';

const dashboardStore = useDashboardStore();
const { overview } = storeToRefs(dashboardStore);
const actions = useDashboardActions();

const topSearches = computed(() => overview.value.top_searches || []);
const maxSearchCount = computed(() =>
  Math.max(1, ...topSearches.value.map((s) => Number(s.count || 0)))
);
const searchPct = (count) => Math.max(6, Math.round((Number(count || 0) / maxSearchCount.value) * 100));
</script>
