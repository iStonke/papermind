<template>
  <div class="sys-gauge" :style="{ width: `${size}px`, height: `${size}px` }">
    <svg :viewBox="`0 0 ${box} ${box}`" class="sys-gauge__svg" aria-hidden="true">
      <circle
        class="sys-gauge__track"
        :cx="center"
        :cy="center"
        :r="radius"
        fill="none"
        :stroke-width="stroke"
      />
      <circle
        class="sys-gauge__value"
        :cx="center"
        :cy="center"
        :r="radius"
        fill="none"
        :stroke="color"
        :stroke-width="stroke"
        stroke-linecap="round"
        :stroke-dasharray="`${arc} ${circumference}`"
        :transform="`rotate(-90 ${center} ${center})`"
      />
    </svg>
    <div class="sys-gauge__label">
      <div class="sys-gauge__value-text" :style="{ color }">{{ display }}</div>
      <div v-if="sublabel" class="sys-gauge__sublabel">{{ sublabel }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  // Füllgrad 0–100 (steuert den Ring)
  percent: { type: Number, default: 0 },
  // Großer Text in der Mitte (z. B. "47 °C" oder "62 %")
  display: { type: [String, Number], default: '' },
  sublabel: { type: String, default: '' },
  color: { type: String, default: 'rgb(var(--v-theme-primary))' },
  size: { type: Number, default: 132 },
  stroke: { type: Number, default: 11 },
});

const box = 120;
const center = box / 2;
const radius = computed(() => center - props.stroke);
const circumference = computed(() => 2 * Math.PI * radius.value);
const clamped = computed(() => Math.max(0, Math.min(100, Number(props.percent) || 0)));
const arc = computed(() => (clamped.value / 100) * circumference.value);
</script>

<style scoped>
.sys-gauge {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.sys-gauge__svg {
  width: 100%;
  height: 100%;
}
.sys-gauge__track {
  stroke: rgba(var(--v-theme-on-surface), 0.1);
}
.sys-gauge__value {
  transition: stroke-dasharray 0.6s ease, stroke 0.4s ease;
}
.sys-gauge__label {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.sys-gauge__value-text {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.sys-gauge__sublabel {
  font-size: 0.68rem;
  opacity: 0.6;
  margin-top: 2px;
  text-align: center;
}
</style>
