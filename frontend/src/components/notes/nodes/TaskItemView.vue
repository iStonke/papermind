<!--
  TaskItemView — schlanke NodeView für Aufgaben (taskItem).
  Erhält den editierbaren Inhalt via NodeViewContent (contentDOM) und ergänzt
  links ausschließlich die runde Checkbox.
-->
<template>
  <node-view-wrapper
    as="li"
    class="pm-taskitem"
    :class="{ 'is-checked': node.attrs.checked }"
    data-type="taskItem"
    :data-checked="node.attrs.checked ? 'true' : 'false'"
  >
    <label class="pm-taskitem__check" contenteditable="false">
      <input
        type="checkbox"
        :checked="node.attrs.checked"
        :disabled="!editor.isEditable"
        :aria-label="node.attrs.checked ? 'Aufgabe als offen markieren' : 'Aufgabe als erledigt markieren'"
        @change="toggle"
      />
    </label>

    <node-view-content class="pm-taskitem__content" as="div" />
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
.pm-taskitem {
  display: flex;
  align-items: flex-start;
  gap: 0.55em;
}

.pm-taskitem__check {
  flex: none;
  display: grid;
  place-items: center;
  height: 1.35em;
  margin: 0;
  cursor: pointer;
}
.pm-taskitem__check input { cursor: pointer; }

.pm-taskitem__content {
  flex: 1 1 auto;
  min-width: 0;
}
.pm-taskitem.is-checked .pm-taskitem__content {
  color: var(--pm-muted, #748084);
  text-decoration: line-through;
  text-decoration-color: color-mix(in srgb, var(--pm-muted, #748084) 60%, transparent);
}
</style>
