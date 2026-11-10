<!--
  CollectionShareBand — Anteil jedes Mitglieds an den Dokumenten einer
  Sammlung als waagerechtes Band (Segmente wachsen beim Öffnen ein), darunter
  die Legende. Ein Klick auf Segment oder Legende klappt das Mitglied in den
  Kacheln auf; das geöffnete Mitglied bleibt hervorgehoben.
-->
<template>
  <div class="csb" :class="{ 'is-ready': ready, 'has-active': Boolean(activeId) }">
    <div class="csb__band" role="presentation">
      <button
        v-for="(seg, index) in segments"
        :key="seg.id"
        type="button"
        tabindex="-1"
        class="csb__seg"
        :class="{ 'is-active': seg.id === activeId }"
        :style="{ '--w': `${seg.share}%`, '--tone': seg.tone, '--i': index }"
        :title="`${seg.name}: ${seg.count} (${Math.round(seg.share)} %)`"
        aria-hidden="true"
        @click="emit('select', seg.id)"
      />
    </div>
    <ul class="csb__legend" aria-label="Anteil je Mitglied">
      <li v-for="seg in segments" :key="seg.id">
        <button
          type="button"
          class="csb__item"
          :class="{ 'is-active': seg.id === activeId }"
          :aria-pressed="seg.id === activeId"
          :style="{ '--tone': seg.tone }"
          @click="emit('select', seg.id)"
        >
          <span class="csb__swatch" aria-hidden="true" />
          <span class="csb__name">{{ seg.name }}</span>
          <span class="csb__count">{{ seg.count }}</span>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { collectionTone } from '../utils/correspondentProfileStats.js';

const props = defineProps({
  collectionId: { type: String, required: true },
  /** collectionMemberSummaries() → { rows, direct } */
  summaries: { type: Object, required: true },
  /** Geöffnetes Mitglied (bzw. collectionId für „Direkt“). */
  activeId: { type: String, default: null },
});
const emit = defineEmits(['select']);

const segments = computed(() => {
  const rows = props.summaries?.rows || [];
  const direct = props.summaries?.direct?.count || 0;
  const total = rows.reduce((sum, r) => sum + r.count, 0) + direct;
  if (!total) return [];
  const list = rows
    .map((row, index) => ({ id: row.id, name: row.name, count: row.count, tone: collectionTone(index) }))
    .filter((s) => s.count > 0);
  if (direct) {
    list.push({
      id: props.collectionId,
      name: 'Direkt',
      count: direct,
      tone: 'color-mix(in srgb, var(--pm-muted) 55%, var(--pm-app-surface))',
    });
  }
  return list.map((s) => ({ ...s, share: (s.count / total) * 100 }));
});

// Segmente wachsen nach dem ersten Zeichnen von 0 auf ihre Breite.
const ready = ref(false);
function replay() {
  ready.value = false;
  requestAnimationFrame(() => requestAnimationFrame(() => { ready.value = true; }));
}
onMounted(replay);
watch(() => props.collectionId, replay);
</script>

<style scoped>
.csb__band { display: flex; gap: 2px; height: 12px; overflow: hidden; border-radius: 6px; }
.csb__seg {
  flex: none;
  width: 0;
  height: 100%;
  padding: 0;
  border: 0;
  border-radius: 2px;
  background: var(--tone);
  cursor: pointer;
  transition: width 900ms cubic-bezier(0.2, 0.8, 0.2, 1), opacity 180ms ease;
  transition-delay: calc(var(--i) * 60ms), 0ms;
}
.csb__seg:first-child { border-radius: 6px 2px 2px 6px; }
.csb__seg:last-child { border-radius: 2px 6px 6px 2px; }
.csb.is-ready .csb__seg { width: calc(var(--w) - 2px); }
.has-active .csb__seg:not(.is-active) { opacity: 0.3; }
.csb__legend { display: flex; flex-wrap: wrap; gap: 2px 6px; margin: 8px 0 0; padding: 0; list-style: none; }
.csb__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 26px;
  padding: 0 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--pm-muted);
  font: inherit;
  font-size: 0.78rem;
  cursor: pointer;
  transition: opacity 180ms ease;
}
.csb__item:hover { background: var(--pm-list-hover); color: var(--pm-text); }
.csb__item:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: 1px; }
.has-active .csb__item:not(.is-active) { opacity: 0.55; }
.csb__item.is-active { color: var(--pm-text); }
.csb__swatch { width: 9px; height: 9px; border-radius: 2px; background: var(--tone); }
.csb__count { color: var(--pm-text); font-variant-numeric: tabular-nums; font-weight: 600; }

@media (prefers-reduced-motion: reduce) { .csb__seg { transition: none; } }
:global(.pm-no-animations) .csb__seg { transition: none; }
</style>
