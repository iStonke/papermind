<template>
  <node-view-wrapper as="section" class="pm-lecture-slide" :class="{ 'is-writing': isWriting }" data-lecture-slide>
    <div class="pm-lecture-slide__header" contenteditable="false">
      <span class="pm-lecture-slide__meta">
        <span>Folie {{ slideNumber }}</span>
        <time v-if="capturedAt" :datetime="capturedAt" :title="captureTitle">· {{ captureDate }} · {{ captureTime }}</time>
      </span>
      <button v-if="editor.isEditable" type="button" class="pm-lecture-slide__remove" title="Zeile entfernen" aria-label="Zeile entfernen" @mousedown.prevent @click="deleteNode()"><v-icon size="16">mdi-trash-can-outline</v-icon></button>
      <button v-if="editor.isEditable && isFirstBlock" type="button" class="pm-lecture-slide__prepend" title="Inhalt oberhalb einfügen" aria-label="Inhalt oberhalb einfügen" @mousedown.prevent @click="addAbove"><v-icon size="16">mdi-plus</v-icon>Inhalt oberhalb</button>
    </div>
    <node-view-content class="pm-lecture-slide__columns" />
    <div v-if="editor.isEditable" class="pm-lecture-slide__footer" contenteditable="false">
      <button type="button" class="pm-lecture-slide__add" title="Screenshot & Mitschrift hinzufügen" aria-label="Screenshot & Mitschrift hinzufügen" @mousedown.prevent @click="addRow"><v-icon size="18" aria-hidden="true">mdi-plus</v-icon></button>
    </div>
  </node-view-wrapper>
</template>
<script setup>
import { computed, nextTick, onBeforeUnmount, ref } from 'vue';
import { NodeViewWrapper, NodeViewContent, nodeViewProps } from '@tiptap/vue-3';
const props = defineProps(nodeViewProps);
const isFirstBlock = ref(false);
const slideNumber = ref(1);
const isWriting = ref(false);
// Cursor in der Mitschrift dieses Abschnitts (bei fokussiertem Editor).
function updateWriting() {
  const pos = props.getPos();
  if (!Number.isInteger(pos) || !props.editor.isFocused) {
    isWriting.value = false;
    return;
  }
  const { $from } = props.editor.state.selection;
  let writing = false;
  for (let depth = $from.depth; depth > 0; depth--) {
    if ($from.node(depth).type.name === 'lectureSlideNotes') {
      writing = $from.before(depth - 1) === pos;
      break;
    }
  }
  isWriting.value = writing;
}
function updatePosition() {
  const pos = props.getPos();
  if (!Number.isInteger(pos)) return;
  isFirstBlock.value = pos === 0;
  let number = 1;
  props.editor.state.doc.nodesBetween(0, pos, (node, nodePos) => {
    if (node.type.name === 'lectureSlide' && nodePos < pos) number++;
  });
  slideNumber.value = number;
}
function onEditorChange() {
  updatePosition();
  updateWriting();
}
onEditorChange();
props.editor.on('transaction', onEditorChange);
props.editor.on('focus', updateWriting);
props.editor.on('blur', updateWriting);
onBeforeUnmount(() => {
  props.editor.off('transaction', onEditorChange);
  props.editor.off('focus', updateWriting);
  props.editor.off('blur', updateWriting);
});
const capturedAt = computed(() => props.node.attrs.capturedAt || null);
const captureDate = computed(() => capturedAt.value
  ? new Date(capturedAt.value).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '');
const captureTime = computed(() => capturedAt.value
  ? new Date(capturedAt.value).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) : '');
const captureTitle = computed(() => capturedAt.value
  ? new Date(capturedAt.value).toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short' }) : '');
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
