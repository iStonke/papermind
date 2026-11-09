<!--
  CorrespondentKeyFigures — Kennzahlen im Korrespondenten-Profil: große, klare
  Zahlen mit kleiner Einheit daneben und einer Zusatzzeile darunter. Beim
  Wechsel des Korrespondenten blenden die Werte nacheinander ein und zählen
  hoch. Bei deaktivierten Animationen (Einstellung oder reduzierte Bewegung)
  stehen sie sofort da.

  items: [{ key, label, count, unit?, text?, sub?, title? }]
    count – Zahl, die hochgezählt wird; ohne count wird `text` gezeigt
-->
<template>
  <dl :key="animationKey" class="pm-figures" :class="[`pm-figures--${layout}`, { 'is-static': reducedMotion }]">
    <div v-for="(item, index) in items" :key="item.key" class="pm-figures__item" :style="{ '--pm-i': index }">
      <dt class="pm-figures__label">{{ item.label }}</dt>
      <dd class="pm-figures__value" :title="item.title || undefined">
        <template v-if="Number.isFinite(item.count)">
          <span class="pm-figures__number">{{ counted[item.key] ?? 0 }}</span>
          <span v-if="item.unit" class="pm-figures__unit">{{ item.unit }}</span>
        </template>
        <span v-else class="pm-figures__number">{{ item.text }}</span>
      </dd>
      <dd v-if="item.sub" class="pm-figures__sub">{{ item.sub }}</dd>
    </div>
  </dl>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue';

const props = defineProps({
  items: { type: Array, default: () => [] },
  /** Wechselt mit dem Korrespondenten und spielt die Einblendung neu ab. */
  animationKey: { type: [String, Number], default: '' },
  /** 'row' (eine Zeile mit Trennern) oder 'grid' (2 × 2, z. B. im Steckbrief). */
  layout: { type: String, default: 'row' },
});

const COUNT_DURATION_MS = 700;

const reducedMotion = ref(false);
const counted = ref({});
let frame = 0;

function prefersReducedMotion() {
  if (typeof window === 'undefined') return true;
  return Boolean(document.querySelector('.papermind-app.pm-no-animations'))
    || Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
}

/** Zahlen von 0 auf ihren Wert hochzählen (ease-out), sonst sofort setzen. */
function runCount() {
  cancelAnimationFrame(frame);
  reducedMotion.value = prefersReducedMotion();
  const targets = Object.fromEntries(props.items.filter((i) => Number.isFinite(i.count)).map((i) => [i.key, i.count]));
  if (reducedMotion.value) {
    counted.value = targets;
    return;
  }
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / COUNT_DURATION_MS);
    const eased = 1 - (1 - t) ** 3;
    counted.value = Object.fromEntries(Object.entries(targets).map(([key, target]) => [key, Math.round(target * eased)]));
    if (t < 1) frame = requestAnimationFrame(step);
  };
  frame = requestAnimationFrame(step);
}

watch(
  () => [props.animationKey, ...props.items.map((i) => `${i.key}:${i.count ?? ''}`)].join('|'),
  runCount,
  { immediate: true }
);
onBeforeUnmount(() => cancelAnimationFrame(frame));
</script>

<style scoped>
.pm-figures {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(0, 1fr);
  margin: 0;
}
.pm-figures__item {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 2px 20px 4px;
  animation: pm-figures-in var(--pm-duration-slow, 340ms) var(--pm-easing-decel) both;
  animation-delay: calc(var(--pm-i, 0) * var(--pm-stagger-step, 45ms) * 1.5);
}
.pm-figures__item:first-child { padding-left: 0; }
.pm-figures__item + .pm-figures__item { border-left: 1px solid var(--pm-divider); }
@keyframes pm-figures-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
.pm-figures.is-static .pm-figures__item { animation: none; }
.pm-figures__label {
  overflow: hidden;
  color: var(--pm-muted);
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-overflow: ellipsis;
  text-transform: uppercase;
  white-space: nowrap;
}
.pm-figures__value {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  margin: 6px 0 0;
  color: var(--pm-text);
  white-space: nowrap;
}
.pm-figures__number {
  min-width: 0;
  overflow: hidden;
  font-size: 2.3rem;
  font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
}
.pm-figures__unit { flex: none; color: var(--pm-muted); font-size: 0.95rem; font-weight: 500; }
.pm-figures__sub {
  margin: 8px 0 0;
  overflow: hidden;
  color: var(--pm-muted);
  font-size: 0.76rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Raster 2 × 2 ohne Trenner, etwas kleiner. */
.pm-figures--grid { grid-auto-flow: row; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 14px; }
.pm-figures--grid .pm-figures__item,
.pm-figures--grid .pm-figures__item + .pm-figures__item { padding: 0; border-left: 0; }
.pm-figures--grid .pm-figures__number { font-size: 1.7rem; }
.pm-figures--grid .pm-figures__unit { font-size: 0.85rem; }

/* Schmale Profilspalte: zwei Spalten, ganz schmal eine. */
@container (max-width: 620px) {
  .pm-figures { grid-auto-flow: row; grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 18px; }
  .pm-figures__item:nth-child(odd) { padding-left: 0; border-left: 0; }
}
@container (max-width: 420px) {
  .pm-figures:not(.pm-figures--grid) { grid-template-columns: minmax(0, 1fr); }
  .pm-figures__item,
  .pm-figures__item + .pm-figures__item { padding-left: 0; border-left: 0; }
}
</style>
