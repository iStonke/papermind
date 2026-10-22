<template>
  <div ref="handle" class="isd-pane-divider" role="separator" tabindex="0" aria-label="Breite der Dokumentdetails ändern" aria-orientation="vertical"
    :aria-valuemin="minimum" :aria-valuemax="maximum" :aria-valuenow="Math.round(modelValue)" :aria-controls="controls"
    title="Ziehen oder Pfeiltasten verwenden · Doppelklick zum Zurücksetzen"
    @pointerdown="start" @pointermove="move" @pointerup="end" @pointercancel="end" @lostpointercapture="end" @keydown="keydown" @dblclick="resize(360)" />
</template>
<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue';
const props = defineProps({ modelValue: Number, controls: String });
const emit = defineEmits(['update:modelValue']);
const handle = ref(null);
const minimum = 300;
const maximum = ref(600);
let drag;
let observer;
let preferred = props.modelValue || 360;
const preference = 'papermind.import.details-width';
function resize(value, persist = true) {
  const width = Math.round(Math.max(minimum, Math.min(maximum.value, value)));
  emit('update:modelValue', width);
  if (persist) { preferred = width; try { localStorage.setItem(preference, String(width)); } catch { /* Optional device preference. */ } }
}
function start(event) {
  if (event.button !== 0) return;
  event.preventDefault();
  drag = { pointer:event.pointerId, x:event.clientX, width:props.modelValue };
  event.currentTarget.setPointerCapture(event.pointerId);
}
function move(event) { if (drag?.pointer === event.pointerId) resize(drag.width + drag.x - event.clientX, false); }
function end(event) { if (drag?.pointer === event.pointerId) { drag = null; resize(props.modelValue); if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); } }
function keydown(event) {
  const value = ({ ArrowLeft:props.modelValue + 20, ArrowRight:props.modelValue - 20, Home:minimum, End:maximum.value })[event.key];
  if (value === undefined) return;
  event.preventDefault(); event.stopPropagation(); resize(value);
}
onMounted(() => {
  const body = handle.value.parentElement;
  const measure = () => { maximum.value = Math.max(minimum, Math.min(600, Math.floor(body.clientWidth * .5), body.clientWidth - 460)); if (body.clientWidth > 900) resize(preferred, false); };
  observer = new ResizeObserver(measure); observer.observe(body); measure();
  try { const stored = Number(localStorage.getItem(preference)); if (stored >= minimum && stored <= 600) { preferred = stored; resize(stored, false); } } catch { /* Keep the default width. */ }
});
onBeforeUnmount(() => observer?.disconnect());
</script>
<style scoped>
.isd-pane-divider { flex:0 0 8px; position:relative; cursor:col-resize; touch-action:none; outline:none; }
.isd-pane-divider::before { content:''; position:absolute; inset:0 3px; background:var(--pm-divider-soft); transition:background .12s; }
.isd-pane-divider:hover::before, .isd-pane-divider:focus-visible::before { background:rgb(var(--v-theme-primary)); }
@media (max-width:960px) { .isd-pane-divider { display:none; } }
</style>
