<template>
  <node-view-wrapper class="pm-lecture-slide__media" :class="{ 'is-empty': isEmpty }" data-lecture-slide-media>
    <!-- Leere Folie: Platzhalter. Einfügen per ⌘V (Cursor in der Mitschrift
         daneben) oder per Klick über die Dateiauswahl. -->
    <button
      v-if="isEmpty"
      class="pm-lecture-slide__drop"
      type="button"
      contenteditable="false"
      :disabled="!editor.isEditable"
      @mousedown.prevent
      @click="requestImage"
    >
      <v-icon size="22">mdi-image-plus-outline</v-icon>
      <span class="pm-lecture-slide__drop-title">Screenshot einfügen</span>
      <span class="pm-lecture-slide__drop-hint">Klicken oder ⌘V in der Mitschrift</span>
    </button>
    <node-view-content class="pm-lecture-slide__media-content" />
  </node-view-wrapper>
</template>

<script setup>
import { computed } from 'vue';
import { NodeViewContent, NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

const props = defineProps(nodeViewProps);

const isEmpty = computed(() => props.node.childCount === 0);

function requestImage() {
  if (!props.editor.isEditable || typeof props.getPos !== 'function') return;
  props.extension.options.onRequestImage?.(props.getPos());
}
</script>
