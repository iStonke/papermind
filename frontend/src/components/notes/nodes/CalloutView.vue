<template>
  <node-view-wrapper
    as="aside"
    class="pm-callout"
    :class="[`is-${kind}`, { 'is-selected': selected, 'is-arriving': isArriving }]"
    :data-callout="kind"
  >
    <header class="pm-callout__head" contenteditable="false">
      <span class="pm-callout__glyph" aria-hidden="true">
        <PmActionIcon :name="meta.icon" :size="18" />
      </span>
      <select
        v-if="editor.isEditable"
        class="pm-callout__kind"
        :value="kind"
        aria-label="Art des Hinweisblocks"
        @mousedown.stop
        @change="changeKind"
      >
        <option v-for="option in NOTE_CALLOUT_OPTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <span v-else class="pm-callout__kind pm-callout__kind--readonly">{{ meta.label }}</span>
    </header>

    <node-view-content class="pm-callout__content" />
  </node-view-wrapper>
</template>

<script setup>
import PmActionIcon from '../../PmActionIcon.vue';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { NodeViewContent, NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';
import {
  NOTE_CALLOUT_OPTIONS,
  normalizeNoteCalloutKind,
  noteCalloutMeta,
} from '../../../utils/noteCallouts.js';

const props = defineProps(nodeViewProps);
const kind = computed(() => normalizeNoteCalloutKind(props.node.attrs.kind));
const meta = computed(() => noteCalloutMeta(kind.value));
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

function changeKind(event) {
  props.updateAttributes({ kind: normalizeNoteCalloutKind(event.target.value) });
}
</script>

<style scoped>
.pm-callout {
  --pm-callout-color: var(--pm-warning, #b7791f);
  position: relative;
  margin: 0.85em 0;
  padding: 11px 14px 12px;
  border: 1px solid color-mix(in srgb, var(--pm-callout-color) 34%, var(--pm-divider, #d8dfe1));
  border-left: 3px solid transparent;
  border-radius: 9px;
  background: color-mix(in srgb, var(--pm-callout-color) 8%, var(--pm-content-surface, #fff));
}

.pm-callout::before {
  content: '';
  position: absolute;
  top: -1px;
  bottom: -1px;
  left: -1px;
  width: 3px;
  border-radius: 9px 0 0 9px;
  background: var(--pm-callout-color);
  pointer-events: none;
  transform-origin: top;
}

.pm-callout.is-arriving::before {
  animation: pm-callout-line-grow 340ms cubic-bezier(0.22, 1, 0.36, 1) both;
}

.pm-callout.is-arriving .pm-callout__glyph {
  animation: pm-callout-glyph-arrive 280ms cubic-bezier(0.16, 1, 0.3, 1) 105ms both;
}

.pm-callout.is-arriving .pm-callout__content {
  animation: pm-callout-content-arrive 320ms ease-out 195ms both;
}

.pm-callout.is-question { --pm-callout-color: var(--pm-accent, #006b75); }
.pm-callout.is-info { --pm-callout-color: #2878b5; }
.pm-callout.is-decision { --pm-callout-color: #2f855a; }
.pm-callout.is-prompt { --pm-callout-color: #7c5aa6; }

.pm-callout.is-selected {
  outline: 2px solid color-mix(in srgb, var(--pm-callout-color) 42%, transparent);
  outline-offset: 2px;
}

.pm-callout__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 6px;
  color: var(--pm-callout-color);
}

.pm-callout__glyph {
  display: inline-grid;
  width: 18px;
  height: 18px;
  flex: none;
  place-items: center;
}

.pm-callout__kind {
  max-width: 180px;
  padding: 2px 18px 2px 0;
  border: 0;
  outline: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.pm-callout__kind--readonly {
  padding-right: 0;
  cursor: default;
}

.pm-callout__content {
  color: var(--pm-text, #0e181b);
}

.pm-callout__content :deep(p:first-child) { margin-top: 0; }
.pm-callout__content :deep(p:last-child) { margin-bottom: 0; }

@keyframes pm-callout-line-grow {
  from { opacity: 0.35; transform: scaleY(0); }
  to { opacity: 1; transform: scaleY(1); }
}

@keyframes pm-callout-glyph-arrive {
  from { opacity: 0; transform: translateY(3px) scale(0.72); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes pm-callout-content-arrive {
  from { opacity: 0; transform: translateY(3px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .pm-callout.is-arriving::before,
  .pm-callout.is-arriving .pm-callout__glyph,
  .pm-callout.is-arriving .pm-callout__content { animation: none; }
}

:global(.pm-no-animations) .pm-callout.is-arriving::before,
:global(.pm-no-animations) .pm-callout.is-arriving .pm-callout__glyph,
:global(.pm-no-animations) .pm-callout.is-arriving .pm-callout__content {
  animation: none;
}
</style>
