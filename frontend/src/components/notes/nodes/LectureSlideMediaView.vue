<template>
  <node-view-wrapper class="pm-lecture-slide__media" :class="{ 'is-empty': isEmpty }" data-lecture-slide-media>
    <!-- Leere Folie: Platzhalter. Einfügen per ⌘V (Cursor in der Mitschrift
         daneben) oder per Klick über die Dateiauswahl. -->
    <div
      v-if="isEmpty"
      ref="dropElement"
      class="pm-lecture-slide__drop"
      :class="{ 'is-active': pasteReady, 'is-dragging': dragDepth > 0 }"
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
      @dragenter.prevent="dragDepth++"
      @dragleave="dragDepth = Math.max(0, dragDepth - 1)"
      @dragover.prevent
      @drop.prevent.stop="dropImage"
    >
      <v-icon size="22">mdi-image-plus-outline</v-icon>
      <span class="pm-lecture-slide__drop-title">Screenshot einfügen <span class="pm-lecture-slide__drop-key">⌘V</span></span>
      <!-- Weitere Wege erst bei Hover/Fokus/Ziehen, damit leere Folien ruhig bleiben. -->
      <span class="pm-lecture-slide__drop-more">
        <span class="pm-lecture-slide__drop-more-inner">
          <span class="pm-lecture-slide__drop-hint">oder Bild hierher ziehen</span>
          <button v-if="editor.isEditable" type="button" class="pm-lecture-slide__choose" @click.stop="requestImage">Datei auswählen</button>
        </span>
      </span>
    </div>
    <node-view-content class="pm-lecture-slide__media-content" />
  </node-view-wrapper>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import { NodeViewContent, NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

const props = defineProps(nodeViewProps);

const isEmpty = computed(() => props.node.childCount === 0);
const dropElement = ref(null);
const pasteReady = ref(false);
const dragDepth = ref(0);
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
function dropImage(event) {
  dragDepth.value = 0;
  insertFiles(event.dataTransfer?.files);
}
</script>
