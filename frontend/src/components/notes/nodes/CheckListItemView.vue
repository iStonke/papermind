<!--
  CheckListItemView — NodeView für neutrale Checklistenpunkte (checkListItem).
  Baugleich zur Aufgaben-NodeView, aber bewusst OHNE Aufgaben-Charakter: keine
  Fälligkeit, kein Durchstreichen. Eckige Checkbox (per CSS) trennt sie optisch
  von der runden Aufgabe. Dieser Node-Typ wird vom Backend nicht als Aufgabe
  erfasst und taucht daher nie in der Aufgaben-Übersicht auf.
-->
<template>
  <node-view-wrapper
    as="li"
    class="pm-checkitem"
    :class="{ 'is-checked': node.attrs.checked }"
    data-type="checkListItem"
    :data-checked="node.attrs.checked ? 'true' : 'false'"
  >
    <label class="pm-checkitem__check" contenteditable="false">
      <input
        type="checkbox"
        :checked="node.attrs.checked"
        :disabled="!editor.isEditable"
        :aria-label="node.attrs.checked ? 'Haken entfernen' : 'Punkt abhaken'"
        @change="toggle"
      />
    </label>

    <node-view-content class="pm-checkitem__content" as="div" />
  </node-view-wrapper>
</template>

<script setup>
import { NodeViewContent, NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

const props = defineProps(nodeViewProps);

function toggle(event) {
  if (!props.editor.isEditable) return;
  props.updateAttributes({ checked: event.target.checked });
}
</script>

<style scoped>
.pm-checkitem {
  display: flex;
  align-items: flex-start;
  gap: 0.55em;
}

.pm-checkitem__check {
  flex: none;
  display: grid;
  place-items: center;
  height: 1.35em;
  margin: 0;
  cursor: pointer;
}
.pm-checkitem__check input { cursor: pointer; }

.pm-checkitem__content {
  flex: 1 1 auto;
  min-width: 0;
}
/* Neutrale Checkliste: abgehakte Punkte werden nur gedämpft, NICHT durchgestrichen
   (kein Aufgaben-Charakter). */
.pm-checkitem.is-checked .pm-checkitem__content {
  color: var(--pm-muted, #748084);
}
</style>
