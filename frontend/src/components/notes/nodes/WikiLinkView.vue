<template>
  <node-view-wrapper
    as="span"
    class="pm-wikilink"
    :class="{ 'is-selected': selected }"
    contenteditable="false"
    :title="`Öffnen: ${node.attrs.label}`"
    @click="open"
  >
    <span class="pm-wikilink__ic" aria-hidden="true">{{ glyph }}</span>
    <span class="pm-wikilink__label">{{ node.attrs.label }}</span>
  </node-view-wrapper>
</template>

<script setup>
import { computed } from 'vue';
import { NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';
import { targetGlyph } from '../mockData.js';

const props = defineProps(nodeViewProps);
const glyph = computed(() => targetGlyph(props.node.attrs.targetType));

function open() {
  window.dispatchEvent(new CustomEvent('pm-note:navigate', {
    detail: { type: props.node.attrs.targetType, id: props.node.attrs.targetId, label: props.node.attrs.label },
  }));
}
</script>

<style scoped>
.pm-wikilink {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  cursor: pointer;
  color: var(--pm-accent-strong, #00555f);
  border-bottom: 1px solid rgba(var(--v-theme-primary, 0 107 117), 0.4);
  line-height: 1.3;
  white-space: nowrap;
}
.pm-wikilink:hover { border-bottom-color: var(--pm-accent, #006b75); background: rgba(var(--v-theme-primary, 0 107 117), 0.08); }
.pm-wikilink.is-selected { outline: 2px solid rgba(var(--v-theme-primary, 0 107 117), 0.45); outline-offset: 1px; border-radius: 3px; }
.pm-wikilink__ic { font-size: 0.8em; opacity: 0.75; }
</style>
