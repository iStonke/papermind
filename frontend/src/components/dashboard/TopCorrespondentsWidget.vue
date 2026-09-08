<!--
  TopCorrespondentsWidget — Rangliste der häufigsten Korrespondenten. Passt die
  Zahl sichtbarer Zeilen per ResizeObserver an die verfügbare Kartenhöhe an, um
  nicht über den Rand zu laufen.
-->
<template>
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
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDashboardStore } from '../../stores/dashboard.js';
import { formatInt, rampColor } from './dashboardShared.js';
import './dashboard.css';

const dashboardStore = useDashboardStore();
const { overview } = storeToRefs(dashboardStore);

const rankListEl = ref(null);
const visibleRankCount = ref(6);
let rankResizeObserver = null;

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

onBeforeUnmount(() => {
  rankResizeObserver?.disconnect();
});
</script>
