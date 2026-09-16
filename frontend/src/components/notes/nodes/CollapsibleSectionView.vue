<template>
  <node-view-wrapper class="pm-section">
    <header class="pm-section__header" contenteditable="false">
      <button type="button" :aria-expanded="isOpen" :aria-label="`${node.attrs.title || 'Abschnitt'} ${isOpen ? 'einklappen' : 'ausklappen'}`" @mousedown.prevent @click="toggle">
        <span aria-hidden="true">{{ isOpen ? '▾' : '▸' }}</span>
      </button>
      <input v-if="editor.isEditable" :value="node.attrs.title" aria-label="Abschnittsüberschrift" placeholder="Abschnitt" @input="updateAttributes({ title: $event.target.value })" @keydown.stop @mousedown.stop />
      <span v-else>{{ node.attrs.title }}</span>
    </header>
    <node-view-content v-show="isOpen" class="pm-section__content" />
  </node-view-wrapper>
</template>
<script setup>
import { computed, ref } from 'vue';
import { NodeViewWrapper, NodeViewContent, nodeViewProps } from '@tiptap/vue-3';
const props = defineProps(nodeViewProps);
const previewOpen = ref(null);
const isOpen = computed(() => props.editor.isEditable ? props.node.attrs.open : (previewOpen.value ?? props.node.attrs.open));
function toggle() {
  if (props.editor.isEditable) props.updateAttributes({ open: !isOpen.value });
  else previewOpen.value = !isOpen.value;
}
</script>
<style scoped>
.pm-section { border: 1px solid var(--pm-divider, #d8dfe1); border-radius: 8px; }
.pm-section__header { display: flex; align-items: center; gap: 8px; padding: 10px 12px; font-weight: 600; }
.pm-section__header button { color: var(--pm-accent, #006b75); width: 28px; height: 28px; cursor: pointer; border-radius: 4px; }
.pm-section__header input { min-width: 0; width: 100%; color: inherit; font: inherit; background: transparent; }
.pm-section__header button:focus-visible, .pm-section__header input:focus-visible { outline: 2px solid var(--pm-accent, #006b75); outline-offset: 2px; }
.pm-section__content { padding: 4px 16px 16px; }
.pm-section__content :deep([data-node-view-content] > * + *) { margin-top: 0.75em; }
@media print { .pm-section__content { display: block !important; } }
</style>
