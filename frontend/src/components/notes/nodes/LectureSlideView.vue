<template>
  <node-view-wrapper as="section" class="pm-lecture-slide" data-lecture-slide>
    <div v-if="editor.isEditable" class="pm-lecture-slide__header" contenteditable="false">
      <button v-if="isFirstBlock" type="button" class="pm-lecture-slide__prepend" title="Inhalt oberhalb einfügen" aria-label="Inhalt oberhalb einfügen" @mousedown.prevent @click="addAbove"><v-icon size="16">mdi-plus</v-icon>Inhalt oberhalb</button>
      <button v-if="editor.isEditable" type="button" class="pm-lecture-slide__remove" title="Zeile entfernen" aria-label="Zeile entfernen" @mousedown.prevent @click="deleteNode()"><v-icon size="16">mdi-trash-can-outline</v-icon></button>
    </div>
    <node-view-content class="pm-lecture-slide__columns" />
    <div v-if="editor.isEditable" class="pm-lecture-slide__footer" contenteditable="false">
      <button type="button" class="pm-lecture-slide__add" title="Screenshot & Mitschrift hinzufügen" aria-label="Screenshot & Mitschrift hinzufügen" @mousedown.prevent @click="addRow"><v-icon size="18" aria-hidden="true">mdi-plus</v-icon></button>
    </div>
  </node-view-wrapper>
</template>
<script setup>
import { nextTick, onBeforeUnmount, ref } from 'vue';
import { NodeViewWrapper, NodeViewContent, nodeViewProps } from '@tiptap/vue-3';
const props = defineProps(nodeViewProps);
const isFirstBlock = ref(props.getPos() === 0);
function updateFirstBlock() { isFirstBlock.value = props.getPos() === 0; }
props.editor.on('transaction', updateFirstBlock);
onBeforeUnmount(() => props.editor.off('transaction', updateFirstBlock));
function addAbove() {
  const pos = props.getPos();
  props.editor.chain().focus().insertContentAt(pos, { type: 'paragraph' }).setTextSelection(pos + 1).run();
}
async function addRow() {
  const pos = props.getPos();
  const newPos = pos + props.node.nodeSize;
  const notesPos = pos + 1 + props.node.firstChild.nodeSize + 1;
  if (!props.editor.chain().focus().setTextSelection(notesPos + 1).insertLectureSlide().run()) return;
  await nextTick();
  if (props.editor.isDestroyed || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const dom = props.editor.view.nodeDOM(newPos);
  const row = dom?.matches?.('.pm-lecture-slide') ? dom : dom?.querySelector?.('.pm-lecture-slide');
  row?.animate([
    { opacity: 0, transform: 'translateY(10px)' },
    { opacity: 1, transform: 'translateY(0)' },
  ], { duration: 240, easing: 'ease-out' });
}
</script>
