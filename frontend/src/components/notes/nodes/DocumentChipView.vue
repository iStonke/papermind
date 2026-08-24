<template>
  <node-view-wrapper
    as="span"
    class="pm-docchip"
    :class="{ 'is-selected': selected, 'is-arriving': isArriving }"
    contenteditable="false"
    :title="`Beleg öffnen: ${node.attrs.title}`"
    @click="open"
  >
    <span class="pm-docchip__ic" aria-hidden="true">▢</span>
    <span class="pm-docchip__label">{{ node.attrs.title || 'Beleg' }}</span>
  </node-view-wrapper>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

const props = defineProps(nodeViewProps);
const insertedAt = Date.parse(props.node.attrs.insertedAt || '');
const isArriving = ref(
  props.editor.isEditable
  && Number.isFinite(insertedAt)
  && Math.abs(Date.now() - insertedAt) <= 4000,
);
let arrivalTimer = null;

onMounted(() => {
  if (!isArriving.value) return;
  arrivalTimer = window.setTimeout(() => {
    isArriving.value = false;
    arrivalTimer = null;
  }, 760);
});

onBeforeUnmount(() => {
  if (arrivalTimer) window.clearTimeout(arrivalTimer);
});

function open() {
  window.dispatchEvent(new CustomEvent('pm-note:navigate', {
    detail: { type: 'document', id: props.node.attrs.docId, label: props.node.attrs.title },
  }));
}
</script>

<style scoped>
.pm-docchip {
  position: relative;
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  padding: 1px 7px;
  border-radius: 6px;
  font-size: 0.92em;
  font-weight: 500;
  line-height: 1.35;
  cursor: pointer;
  background: var(--pm-accent-wash, rgba(0, 107, 117, 0.1));
  color: var(--pm-accent-strong, #00555f);
  border: 1px solid rgba(var(--v-theme-primary, 0 107 117), 0.32);
  transition: background 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
  white-space: nowrap;
  transform-origin: left center;
}
.pm-docchip.is-arriving {
  animation: pm-docchip-arrive 420ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
.pm-docchip.is-arriving::after {
  content: '';
  position: absolute;
  inset: -2px;
  border: 1px solid color-mix(in srgb, var(--pm-accent, #006b75) 48%, transparent);
  border-radius: 8px;
  pointer-events: none;
  animation: pm-docchip-ring 720ms ease-out both;
}
.pm-docchip.is-arriving .pm-docchip__ic {
  animation: pm-docchip-icon 500ms cubic-bezier(0.16, 1, 0.3, 1) 70ms both;
}
.pm-docchip:hover { background: rgba(var(--v-theme-primary, 0 107 117), 0.18); }
.pm-docchip.is-selected {
  outline: 2px solid rgba(var(--v-theme-primary, 0 107 117), 0.55);
  outline-offset: 1px;
}
.pm-docchip__ic { font-size: 0.85em; }

@keyframes pm-docchip-arrive {
  from { opacity: 0; transform: translateY(5px) scale(0.88); }
  72% { opacity: 1; transform: translateY(-1px) scale(1.035); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes pm-docchip-ring {
  0% {
    opacity: 0;
    transform: scale(0.9);
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--pm-accent, #006b75) 24%, transparent);
  }
  38% { opacity: 1; }
  100% {
    opacity: 0;
    transform: scale(1.08);
    box-shadow: 0 0 0 5px transparent;
  }
}

@keyframes pm-docchip-icon {
  0% { opacity: 0; transform: scale(0.65); }
  55% { opacity: 1; transform: scale(1.18); filter: drop-shadow(0 0 4px color-mix(in srgb, var(--pm-accent, #006b75) 42%, transparent)); }
  100% { opacity: 1; transform: scale(1); filter: none; }
}

@media (prefers-reduced-motion: reduce) {
  .pm-docchip { transition: none; }
  .pm-docchip.is-arriving,
  .pm-docchip.is-arriving::after,
  .pm-docchip.is-arriving .pm-docchip__ic { animation: none; }
}

:global(.pm-no-animations) .pm-docchip,
:global(.pm-no-animations) .pm-docchip.is-arriving,
:global(.pm-no-animations) .pm-docchip.is-arriving::after,
:global(.pm-no-animations) .pm-docchip.is-arriving .pm-docchip__ic {
  animation: none;
  transition: none;
}
</style>
