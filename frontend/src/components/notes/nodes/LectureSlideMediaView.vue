<template>
  <node-view-wrapper class="pm-lecture-slide__media" :class="{ 'is-empty': isEmpty }" data-lecture-slide-media>
    <!-- Leere Folie: Platzhalter. Einfügen per ⌘V (Cursor in der Mitschrift
         daneben) oder per Klick über die Dateiauswahl. -->
    <div
      v-if="isEmpty"
      ref="dropElement"
      class="pm-lecture-slide__drop"
      :class="{ 'is-active': pasteReady }"
      role="button"
      tabindex="0"
      contenteditable="false"
      :aria-disabled="!editor.isEditable"
      :aria-pressed="pasteReady"
      @click="activatePaste"
      @focusin="pasteReady = editor.isEditable"
      @focusout="leavePasteFocus"
      @keydown.enter.prevent="requestImage"
      @paste.stop="pasteImage"
      @dragover.prevent
      @drop.prevent.stop="dropImage"
    >
      <v-icon size="22">mdi-image-plus-outline</v-icon>
      <span class="pm-lecture-slide__drop-title">Screenshot einfügen</span>
      <span class="pm-lecture-slide__drop-hint">⌘V oder Bild hierher ziehen</span>
      <button v-if="editor.isEditable" type="button" class="pm-lecture-slide__choose" @click.stop="requestImage">Datei auswählen</button>
    </div>
    <node-view-content class="pm-lecture-slide__media-content" />
    <time v-if="isEmpty && capturedAt" class="pm-lecture-slide__capture" :datetime="capturedAt">{{ captureLabel }}</time>
  </node-view-wrapper>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { useLectureCapture } from './useLectureCapture.js';
import { NodeViewContent, NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

const props = defineProps(nodeViewProps);
const { capturedAt, captureLabel } = useLectureCapture(props);

const isEmpty = computed(() => props.node.childCount === 0);
const dropElement = ref(null);
const pasteReady = ref(false);
function activatePaste(event) {
  if (!props.editor.isEditable) return;
  pasteReady.value = true;
  event.currentTarget.focus({ preventScroll: true });
}
function clearPasteReady() {
  pasteReady.value = false;
  if (dropElement.value?.contains(document.activeElement)) document.activeElement.blur();
}
function outsidePointerDown(event) {
  if (pasteReady.value && !dropElement.value?.contains(event.target)) clearPasteReady();
}
function leavePasteFocus(event) {
  if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) pasteReady.value = false;
}
watch(isEmpty, empty => { if (!empty) pasteReady.value = false; });
onMounted(() => document.addEventListener('pointerdown', outsidePointerDown, true));
onBeforeUnmount(() => document.removeEventListener('pointerdown', outsidePointerDown, true));

function requestImage() {
  if (!props.editor.isEditable || typeof props.getPos !== 'function') return;
  props.extension.options.onRequestImage?.(props.getPos());
}
function insertFiles(files) {
  if (!props.editor.isEditable) return false;
  const images = Array.from(files || []).filter(file => file.type.startsWith('image/'));
  if (!images.length) return false;
  props.extension.options.onPasteImage?.(props.getPos(), images);
  return true;
}
function pasteImage(event) {
  if (insertFiles(event.clipboardData?.files)) event.preventDefault();
}
function dropImage(event) { insertFiles(event.dataTransfer?.files); }
</script>
