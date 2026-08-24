<template>
  <node-view-wrapper
    class="pm-ocrquote"
    :class="{ 'is-selected': selected }"
    contenteditable="false"
  >
    <p class="pm-ocrquote__text">{{ node.attrs.text }}</p>
    <button class="pm-ocrquote__src" type="button" @click="open">
      <span aria-hidden="true">▢</span>
      {{ node.attrs.docTitle }}<template v-if="node.attrs.page"> · S.&nbsp;{{ node.attrs.page }}</template>
      <span class="pm-ocrquote__origin">· aus Markierung übernommen</span>
    </button>
  </node-view-wrapper>
</template>

<script setup>
import { NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

const props = defineProps(nodeViewProps);

function open() {
  window.dispatchEvent(new CustomEvent('pm-note:navigate', {
    detail: {
      type: 'document', id: props.node.attrs.docId,
      label: props.node.attrs.docTitle, page: props.node.attrs.page,
    },
  }));
}
</script>

<style scoped>
.pm-ocrquote {
  border-left: 2.5px solid var(--pm-accent, #006b75);
  background: var(--pm-viewer-surface, #eef2f4);
  border-radius: 0 10px 10px 0;
  padding: 12px 16px;
  margin: 0.7em 0;
}
.pm-ocrquote.is-selected {
  outline: 2px solid rgba(var(--v-theme-primary, 0 107 117), 0.45);
  outline-offset: 2px;
}
.pm-ocrquote__text {
  margin: 0 0 8px;
  font-style: italic;
  color: var(--pm-text, #0e181b);
  line-height: 1.55;
}
.pm-ocrquote__src {
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.72rem;
  color: var(--pm-muted, #535e62);
  text-align: left;
}
.pm-ocrquote__src:hover { color: var(--pm-accent-strong, #00555f); }
.pm-ocrquote__origin { opacity: 0.8; }
</style>
