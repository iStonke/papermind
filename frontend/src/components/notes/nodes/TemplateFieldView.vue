<template>
  <node-view-wrapper
    as="div"
    class="pm-tf"
    :class="{ 'is-empty': isEmpty }"
    :data-template-field="''"
  >
    <div class="pm-tf__label" contenteditable="false">
      <input
        v-if="editor.isEditable"
        ref="labelInput"
        class="pm-tf__label-input"
        type="text"
        :value="label"
        placeholder="Feld"
        aria-label="Feldname"
        spellcheck="false"
        @mousedown.stop
        @keydown.stop
        @input="onLabelInput"
      />
      <span v-else class="pm-tf__label-text">{{ label }}</span>
    </div>

    <div class="pm-tf__value">
      <node-view-content class="pm-tf__content" />
      <span v-if="isEmpty && hint" class="pm-tf__hint" contenteditable="false" aria-hidden="true">{{ hint }}</span>
    </div>

    <div v-if="editor.isEditable" class="pm-tf__actions" contenteditable="false">
      <button
        type="button"
        class="pm-tf__act"
        title="Zeile hinzufügen"
        aria-label="Zeile hinzufügen"
        @mousedown.prevent.stop
        @click="addRowBelow"
      >＋</button>
      <button
        type="button"
        class="pm-tf__act pm-tf__act--danger"
        title="Zeile entfernen"
        aria-label="Zeile entfernen"
        @mousedown.prevent.stop
        @click="removeRow"
      >✕</button>
    </div>
  </node-view-wrapper>
</template>

<script setup>
import { computed, ref } from 'vue';
import { NodeViewContent, NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';
import { newTemplateFieldAttrs } from './noteTemplates.js';

const props = defineProps(nodeViewProps);
const labelInput = ref(null);

const label = computed(() => props.node.attrs.label || '');
const hint = computed(() => props.node.attrs.hint || '');
const isEmpty = computed(() => props.node.content.size === 0);

function onLabelInput(event) {
  props.updateAttributes({ label: event.target.value });
}

// Neue Feldzeile direkt unter dieser Zeile einfügen und hineinspringen.
function addRowBelow() {
  const pos = typeof props.getPos === 'function' ? props.getPos() : null;
  if (pos == null) return;
  const at = pos + props.node.nodeSize;
  props.editor
    .chain()
    .insertContentAt(at, { type: 'templateField', attrs: newTemplateFieldAttrs() })
    .setTextSelection(at + 1)
    .focus()
    .run();
}

// Diese Zeile entfernen. Ist es die letzte Zeile des Blocks, wird der ganze
// Block entfernt (templateBox verlangt mindestens ein Feld).
function removeRow() {
  const pos = typeof props.getPos === 'function' ? props.getPos() : null;
  if (pos == null) return;
  const $pos = props.editor.state.doc.resolve(pos);
  const box = $pos.parent;
  if (box?.type.name === 'templateBox' && box.childCount <= 1) {
    const boxBefore = $pos.before();
    props.editor
      .chain()
      .focus()
      .deleteRange({ from: boxBefore, to: boxBefore + box.nodeSize })
      .run();
    return;
  }
  props.deleteNode();
}
</script>

<style scoped>
.pm-tf {
  /* Etwas hellere, entsättigte Box-Farbe für ALLE Titel (benannt wie Platzhalter). */
  --pm-tf-label: color-mix(in srgb, var(--pm-tpl-color, #0f6e56) 58%, var(--pm-muted, #8a969b));
  position: relative;
  display: grid;
  grid-template-columns: var(--pm-tf-label-w, 104px) 1fr;
  align-items: baseline;
  column-gap: 12px;
  padding: 3px 0;
}

.pm-tf + .pm-tf {
  border-top: 1px dashed color-mix(in srgb, var(--pm-tpl-color, #0f6e56) 16%, var(--pm-divider, #d8dfe1));
}

.pm-tf__label {
  padding-top: 1px;
  user-select: none;
}

.pm-tf__label-input {
  width: 100%;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--pm-tf-label);
  font: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.pm-tf__label-input::placeholder {
  color: var(--pm-tf-label);
  opacity: 1;
  font-weight: 600;
}

.pm-tf__label-text {
  color: var(--pm-tf-label);
  font-size: 0.82rem;
  font-weight: 600;
}

.pm-tf__value {
  position: relative;
  min-width: 0;
}

.pm-tf__content {
  color: var(--pm-text, #0e181b);
  min-height: 1.4em;
}

.pm-tf__content :deep(p) {
  margin: 0;
}

.pm-tf__hint {
  position: absolute;
  inset: 0;
  color: var(--pm-muted, #8a969b);
  font-style: italic;
  opacity: 0.72;
  pointer-events: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pm-tf__actions {
  position: absolute;
  top: 50%;
  right: -8px;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 1px;
  padding: 2px;
  border-radius: 8px;
  background: var(--pm-content-surface, #fff);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--pm-tpl-color, #0f6e56) 20%, var(--pm-divider, #d8dfe1));
  opacity: 0;
  pointer-events: none;
  transition: opacity 120ms ease;
}

.pm-tf:hover .pm-tf__actions,
.pm-tf:focus-within .pm-tf__actions {
  opacity: 1;
  pointer-events: auto;
}

.pm-tf__act {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--pm-muted, #8a969b);
  font-size: 0.78rem;
  line-height: 1;
  cursor: pointer;
  transition: color 120ms ease, background 120ms ease;
}

.pm-tf__act:hover {
  color: var(--pm-tpl-color, #0f6e56);
  background: color-mix(in srgb, var(--pm-tpl-color, #0f6e56) 12%, transparent);
}

.pm-tf__act--danger:hover {
  color: var(--pm-danger, #c0392b);
  background: color-mix(in srgb, var(--pm-danger, #c0392b) 12%, transparent);
}

@media (prefers-reduced-motion: reduce) {
  .pm-tf__actions { transition: none; }
}
</style>
