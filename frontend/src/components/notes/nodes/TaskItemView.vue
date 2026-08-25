<!--
  TaskItemView — NodeView für Aufgaben (taskItem) mit Fälligkeitsdatum.
  Erhält den editierbaren Inhalt via NodeViewContent (contentDOM), ergänzt links
  die Checkbox und rechts einen Kalender-Chip. Der Chip öffnet ein natives
  <input type="date"> (kein Vuetify-Teleport, das im ProseMirror-Kontext stört).
  Das Datum liegt im dueDate-Attribut → Backend extrahiert es nach note_task.
-->
<template>
  <node-view-wrapper
    as="li"
    class="pm-taskitem"
    :class="{ 'is-checked': node.attrs.checked, 'is-overdue': isOverdue }"
    data-type="taskItem"
    :data-checked="node.attrs.checked ? 'true' : 'false'"
  >
    <label class="pm-taskitem__check" contenteditable="false">
      <input
        type="checkbox"
        :checked="node.attrs.checked"
        :disabled="!editor.isEditable"
        @change="toggle"
      />
    </label>

    <node-view-content class="pm-taskitem__content" as="div" />

    <span class="pm-taskitem__due" contenteditable="false">
      <input
        v-if="editing"
        ref="dateInputRef"
        type="date"
        class="pm-taskitem__due-input"
        :value="node.attrs.dueDate || ''"
        @change="commit"
        @blur="stopEditing"
        @keydown.esc.prevent="stopEditing"
      />
      <template v-else>
        <button
          type="button"
          class="pm-taskitem__due-btn"
          :class="{ 'has-date': !!node.attrs.dueDate, 'is-overdue': isOverdue }"
          :title="node.attrs.dueDate ? 'Fälligkeit ändern' : 'Fälligkeitsdatum setzen'"
          :disabled="!editor.isEditable"
          @click="startEditing"
        >
          <v-icon size="13">mdi-calendar-clock</v-icon>
          <span v-if="node.attrs.dueDate" class="pm-taskitem__due-label">{{ dueLabel }}</span>
          <span v-else class="pm-taskitem__due-add">Datum</span>
        </button>
        <button
          v-if="node.attrs.dueDate && editor.isEditable"
          type="button"
          class="pm-taskitem__due-clear"
          aria-label="Fälligkeit entfernen"
          title="Fälligkeit entfernen"
          @click="clearDate"
        >
          <v-icon size="12">mdi-close</v-icon>
        </button>
      </template>
    </span>
  </node-view-wrapper>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue';
import { NodeViewContent, NodeViewWrapper, nodeViewProps } from '@tiptap/vue-3';

const props = defineProps(nodeViewProps);

const editing = ref(false);
const dateInputRef = ref(null);

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const isOverdue = computed(() => {
  const due = props.node.attrs.dueDate;
  return Boolean(due && !props.node.attrs.checked && due < todayIso());
});

const dueLabel = computed(() => {
  const due = props.node.attrs.dueDate;
  if (!due) return '';
  const d = new Date(`${due}T00:00:00`);
  if (Number.isNaN(d.getTime())) return due;
  const now = new Date();
  return d.toLocaleDateString('de-DE', {
    day: 'numeric',
    month: 'short',
    ...(d.getFullYear() === now.getFullYear() ? {} : { year: 'numeric' }),
  });
});

function toggle(event) {
  if (!props.editor.isEditable) return;
  props.updateAttributes({ checked: event.target.checked });
}

async function startEditing() {
  if (!props.editor.isEditable) return;
  editing.value = true;
  await nextTick();
  const el = dateInputRef.value;
  if (el) {
    el.focus();
    if (typeof el.showPicker === 'function') {
      try { el.showPicker(); } catch { /* showPicker kann werfen, wenn nicht erlaubt */ }
    }
  }
}

function stopEditing() {
  editing.value = false;
}

function commit(event) {
  const value = event.target.value || null;
  props.updateAttributes({ dueDate: value });
  editing.value = false;
}

function clearDate() {
  props.updateAttributes({ dueDate: null });
}
</script>

<style scoped>
.pm-taskitem {
  display: flex;
  align-items: flex-start;
  gap: 0.55em;
}

.pm-taskitem__check {
  margin-top: 0.28em;
  flex: none;
  cursor: pointer;
}
.pm-taskitem__check input { accent-color: var(--pm-accent, #006b75); cursor: pointer; }

.pm-taskitem__content {
  flex: 1 1 auto;
  min-width: 0;
}
.pm-taskitem.is-checked .pm-taskitem__content {
  color: var(--pm-muted, #748084);
  text-decoration: line-through;
  text-decoration-color: color-mix(in srgb, var(--pm-muted, #748084) 60%, transparent);
}

.pm-taskitem__due {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-top: 0.16em;
  user-select: none;
}

.pm-taskitem__due-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 7px 1px 6px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--pm-muted, #748084);
  font: inherit;
  font-size: 0.74em;
  line-height: 1.5;
  cursor: pointer;
  opacity: 0.55;
  transition: opacity 120ms ease, background 120ms ease, border-color 120ms ease, color 120ms ease;
}
.pm-taskitem:hover .pm-taskitem__due-btn,
.pm-taskitem__due-btn.has-date { opacity: 1; }
.pm-taskitem__due-btn:hover {
  background: var(--pm-viewer-surface, rgba(0, 0, 0, 0.05));
  color: var(--pm-text, #0e181b);
}
.pm-taskitem__due-btn.has-date {
  border-color: var(--pm-divider, #d8dfe1);
  color: var(--pm-text, #0e181b);
}
.pm-taskitem__due-btn.is-overdue {
  border-color: color-mix(in srgb, var(--pm-danger, #c2453b) 45%, transparent);
  background: color-mix(in srgb, var(--pm-danger, #c2453b) 10%, transparent);
  color: var(--pm-danger, #c2453b);
  opacity: 1;
}
.pm-taskitem__due-add { font-style: italic; }
.pm-taskitem__due-label { font-variant-numeric: tabular-nums; }

.pm-taskitem__due-clear {
  display: inline-flex;
  align-items: center;
  padding: 1px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--pm-muted, #748084);
  cursor: pointer;
  opacity: 0;
  transition: opacity 120ms ease, color 120ms ease;
}
.pm-taskitem:hover .pm-taskitem__due-clear { opacity: 0.7; }
.pm-taskitem__due-clear:hover { color: var(--pm-danger, #c2453b); opacity: 1; }

.pm-taskitem__due-input {
  font: inherit;
  font-size: 0.78em;
  padding: 1px 4px;
  border: 1px solid var(--pm-accent, #006b75);
  border-radius: 6px;
  background: var(--pm-app-surface, #fff);
  color: var(--pm-text, #0e181b);
  color-scheme: light dark;
}

@media (prefers-reduced-motion: reduce) {
  .pm-taskitem__due-btn,
  .pm-taskitem__due-clear { transition: none; }
}
</style>
