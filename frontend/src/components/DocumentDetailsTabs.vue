<template>
  <nav ref="scrollEl" class="details-tabs" aria-label="Dokumentabschnitte">
    <div ref="trackEl" class="details-tabs__track" role="tablist" aria-label="Dokumentabschnitte">
      <button v-for="tab in tabs" :id="`${panelId}-tab-${tab.id}`" :key="tab.id"
        :ref="el => setTabRef(tab.id, el)" type="button" role="tab" class="details-tabs__tab"
        :aria-selected="activeTab === tab.id" :aria-expanded="isOpen && activeTab === tab.id"
        :aria-controls="`${panelId}-${tab.id}`" :tabindex="activeTab === tab.id ? 0 : -1"
        @click="select(tab.id)" @keydown="onKeydown($event, tab.id)">
        {{ tab.label }}
      </button>
      <span class="details-tabs__indicator" :style="indicatorStyle" aria-hidden="true" />
    </div>
  </nav>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
const props = defineProps({ tabs: { type: Array, required: true }, activeTab: String, panelId: { type: String, required: true }, isOpen: Boolean });
const emit = defineEmits(['select']);
const scrollEl = ref(null), trackEl = ref(null);
const buttons = new Map();
const position = ref({ left: 0, width: 0 });
let observer;
function setTabRef(id, el) { if (el) buttons.set(id, el); else buttons.delete(id); }
function measure() {
  const active = buttons.get(props.activeTab);
  if (active) position.value = { left: active.offsetLeft, width: active.offsetWidth };
}
function revealActive() {
  measure();
  const active = buttons.get(props.activeTab), scroll = scrollEl.value;
  if (!active || !scroll) return;
  const rect = active.getBoundingClientRect(), bounds = scroll.getBoundingClientRect();
  if (rect.left < bounds.left) scroll.scrollLeft -= bounds.left - rect.left + 12;
  else if (rect.right > bounds.right) scroll.scrollLeft += rect.right - bounds.right + 12;
}
function select(id) { emit('select', id); }
function onKeydown(event, id) {
  const index = props.tabs.findIndex(tab => tab.id === id), count = props.tabs.length;
  let next;
  if (event.key === 'ArrowRight') next = (index + 1) % count;
  else if (event.key === 'ArrowLeft') next = (index + count - 1) % count;
  else if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = count - 1;
  else return;
  event.preventDefault();
  const target = props.tabs[next].id;
  buttons.get(target)?.focus();
  select(target);
}
const indicatorStyle = computed(() => ({ width: `${position.value.width}px`, transform: `translateX(${position.value.left}px)` }));
watch(() => [props.activeTab, props.tabs], () => { void nextTick(revealActive); }, { deep: true });
onMounted(() => {
  observer = new ResizeObserver(measure);
  observer.observe(trackEl.value);
  measure();
});
onBeforeUnmount(() => observer?.disconnect());
</script>
<style scoped>
.details-tabs { flex: 0 0 auto; overflow-x: auto; scrollbar-width: none; border-bottom: 1px solid var(--pm-divider-soft, var(--pm-divider)); }
.details-tabs::-webkit-scrollbar { display: none; }
.details-tabs__track { position: relative; display: flex; gap: 24px; width: max-content; min-width: min(100%, 960px); margin-inline: auto; padding-inline: 28px; }
.details-tabs__tab { position: relative; flex-shrink: 0; padding: 12px 2px 13px; border: 0; background: transparent; color: var(--pm-muted); cursor: pointer; font: inherit; font-size: 12px; font-weight: 600; line-height: 18px; white-space: nowrap; transition: color 160ms ease; }
.details-tabs__tab:hover, .details-tabs__tab[aria-selected='true'] { color: var(--pm-accent); }
.details-tabs__tab:focus-visible { outline: 2px solid var(--pm-accent); outline-offset: -4px; border-radius: 6px; }
.details-tabs__indicator { position: absolute; left: 0; bottom: 0; height: 2px; border-radius: 2px; background: var(--pm-accent); pointer-events: none; transition: transform 300ms cubic-bezier(.22, 1, .36, 1), width 240ms ease; }
@container (max-width: 660px) { .details-tabs__track { padding-inline: 18px; gap: 18px; } }
:global(.pm-no-animations .details-tabs__tab), :global(.pm-no-animations .details-tabs__indicator) { transition: none; }
@media (prefers-reduced-motion: reduce) { .details-tabs__tab, .details-tabs__indicator { transition: none; } }
</style>
