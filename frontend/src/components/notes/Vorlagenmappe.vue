<!--
  Vorlagenmappe — Verwaltungsfläche für beide Vorlagen-Arten, gleichrangig:
  „Schnellblöcke" (Feldblöcke fürs /-Menü) und „Startnotizen" (ganze Notizen als
  Gerüst). Segment-Filter, zwei identisch aufgebaute Abschnitte mit einheitlichen
  Karten (VorlagenCard), Geisterkarten im Leerzustand, Schnellblock-Editor (Modal)
  und Löschbestätigung. Umsetzung des „Vorlagenmappe"-Entwurfs mit PaperMind-Tokens.
-->
<template>
  <div class="vm">
    <div class="vm__sections">
      <!-- Schnellblöcke -->
      <section class="vm__section">
        <header class="vm__sechead">
          <div class="vm__sectitle">
            <span class="vm__secicon vm__secicon--block" aria-hidden="true"><v-icon size="17">mdi-view-agenda-outline</v-icon></span>
            <h3 class="vm__secname">Schnellblöcke</h3>
            <span v-if="blockTemplates.length" class="vm__count">{{ blockTemplates.length }}</span>
          </div>
        </header>

        <div class="vm__grid" :class="{ 'vm__grid--ghost': !blockTemplates.length }">
          <VorlagenCard
            v-for="tpl in blockTemplates"
            :key="tpl.id"
            variant="schnellblock"
            :title="tpl.name || tpl.title"
            :accent="colorHex(tpl.color)"
            :fields="tpl.fields"
            @edit="openEditBlock(tpl)"
            @delete="confirmDeleteBlock(tpl)"
          />
          <template v-if="!blockTemplates.length">
            <div v-for="i in 3" :key="i" class="vg vg--block" :style="{ '--vg-accent': ghostBlockAccents[(i - 1) % ghostBlockAccents.length] }" aria-hidden="true">
              <div class="vg__preview">
                <span class="vg__row"><span class="vg__pill" /><span class="vg__line" /></span>
                <span class="vg__row"><span class="vg__pill" /><span class="vg__line" /></span>
              </div>
              <div class="vg__meta"><span class="vg__chip" /><span class="vg__name" /></div>
            </div>
          </template>
          <GhostAddCard
            :title="blockTemplates.length ? 'Neuer Schnellblock' : 'Noch kein Schnellblock'"
            subtitle="Neuen Schnellblock anlegen"
            @click="openCreateBlock"
          />
        </div>
      </section>

      <!-- Startnotizen -->
      <section class="vm__section">
        <header class="vm__sechead">
          <div class="vm__sectitle">
            <span class="vm__secicon" aria-hidden="true"><v-icon size="17">mdi-note-outline</v-icon></span>
            <h3 class="vm__secname">Startnotizen</h3>
            <span v-if="startnotizen.length" class="vm__count">{{ startnotizen.length }}</span>
          </div>
        </header>

        <div class="vm__grid" :class="{ 'vm__grid--ghost': !startnotizen.length }">
          <VorlagenCard
            v-for="tpl in startnotizen"
            :key="tpl.id"
            variant="startnotiz"
            :title="tpl.title"
            :accent="neutralAccent"
            @primary="startNote(tpl)"
            @edit="editStartnotiz(tpl)"
            @delete="confirmDeleteStart(tpl)"
          />
          <template v-if="!startnotizen.length">
            <div v-for="i in 3" :key="i" class="vg vg--start" aria-hidden="true">
              <div class="vg__preview vg__preview--page">
                <span class="vg__pline" style="width: 84%" />
                <span class="vg__pline" style="width: 62%" />
                <span class="vg__pline" style="width: 46%" />
              </div>
              <div class="vg__meta"><span class="vg__chip" /><span class="vg__name" /></div>
            </div>
          </template>
          <GhostAddCard
            :title="startnotizen.length ? 'Neue Startnotiz' : 'Noch keine Startnotiz'"
            subtitle="Neue Startnotiz anlegen"
            :disabled="busy"
            @click="createStartnotiz"
          />
        </div>
      </section>
    </div>

    <div v-if="editorOpen" class="vm-modal" @mousedown.self="closeEditor">
      <div class="vm-modal__card" role="dialog" aria-modal="true">
        <div class="vm-modal__title">
          <v-icon size="18">mdi-view-agenda-outline</v-icon>
          {{ editingId ? 'Schnellblock bearbeiten' : 'Neuer Schnellblock' }}
        </div>
        <div class="vm-modal__two">
          <label class="vm-modal__row">
            <span class="vm-modal__label">Name</span>
            <input ref="nameInput" v-model="draft.name" class="vm-modal__input" type="text" placeholder="z. B. Telefonnotiz" @keydown.enter.prevent="focusFirstField" />
          </label>
          <label class="vm-modal__row">
            <span class="vm-modal__label">Titel in der Box</span>
            <input v-model="draft.title" class="vm-modal__input" type="text" placeholder="Überschrift der Box" />
          </label>
        </div>
        <div class="vm-modal__row">
          <span class="vm-modal__label">Farbe</span>
          <div class="vm-modal__colors">
            <button
              v-for="c in colors"
              :key="c.key"
              type="button"
              class="vm-modal__swatch"
              :class="{ 'is-active': c.key === draft.color }"
              :style="{ '--sw': c.hex }"
              :title="c.label"
              :aria-label="`Farbe ${c.label}`"
              @click="draft.color = c.key"
            ></button>
          </div>
        </div>
        <div class="vm-modal__fields" :style="{ '--c': colorHex(draft.color) }">
          <div class="vm-modal__fieldshead">
            <span class="vm-modal__label">Felder</span>
            <span class="vm-modal__fieldshint">Label &amp; Platzhalter</span>
          </div>
          <div v-for="(field, index) in draft.fields" :key="index" class="vm-field">
            <span class="vm-field__bar" aria-hidden="true" />
            <input :ref="index === 0 ? 'firstFieldInput' : undefined" v-model="field.label" class="vm-field__input" type="text" placeholder="Label (z. B. Datum)" />
            <input v-model="field.hint" class="vm-field__input" type="text" placeholder="Platzhalter (z. B. tt.mm.jjjj)" />
            <button type="button" class="vm-field__del" title="Feld entfernen" aria-label="Feld entfernen" @click="removeField(index)">
              <v-icon size="15">mdi-trash-can-outline</v-icon>
            </button>
          </div>
          <button type="button" class="vm-addfield" @click="addField">
            <v-icon size="16">mdi-plus</v-icon> Feld hinzufügen
          </button>
        </div>
        <div class="vm-modal__actions">
          <button type="button" class="vm-btn" @click="closeEditor">Abbrechen</button>
          <button type="button" class="vm-btn vm-btn--primary" :disabled="saving || !draft.name.trim()" @click="saveBlock">
            {{ saving ? 'Speichert …' : 'Speichern' }}
          </button>
        </div>
      </div>
    </div>

    <DestructiveDialog
      v-model="confirm.open"
      :title="confirm.title"
      :header-subtitle="confirm.subtitle"
      :primary-text="confirm.primaryText"
      secondary-text="Zurück"
      icon="mdi-trash-can-outline"
      :max-width="480"
      :loading="busy"
      :persistent="busy"
      @primary="confirm.onPrimary"
      @close="closeConfirm"
    />
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useNotesStore } from '../../stores/notes.js';
import { notifyError, useNotifications } from '../../stores/notifications.js';
import { createNote as apiCreateNote } from '../../api/notes.js';
import { NOTE_TEMPLATE_COLORS, templateColorHex } from './nodes/noteTemplates.js';
import VorlagenCard from './VorlagenCard.vue';
import GhostAddCard from './GhostAddCard.vue';
import DestructiveDialog from '../DestructiveDialog.vue';

const emit = defineEmits(['open-note', 'changed']);

const notesStore = useNotesStore();
const { notify } = useNotifications();
const { blockTemplates, templates: startnotizen } = storeToRefs(notesStore);

const colors = NOTE_TEMPLATE_COLORS;
const neutralAccent = templateColorHex('neutral');
const ghostBlockAccents = [
  templateColorHex('teal'),
  templateColorHex('blau'),
  templateColorHex('bernstein'),
  templateColorHex('gruen'),
];

const busy = ref(false);

onMounted(() => {
  notesStore.ensureBlockTemplatesLoaded?.();
  notesStore.ensureTemplatesLoaded?.();
});

function colorHex(key) {
  return templateColorHex(key);
}

/* ── Schnellblock-Editor ────────────────────────────────────────────────── */
const editorOpen = ref(false);
const editingId = ref(null);
const saving = ref(false);
const nameInput = ref(null);
const firstFieldInput = ref(null);
const draft = reactive({ name: '', title: '', color: 'teal', fields: [] });

function resetDraft({ name = '', title = '', color = 'teal', fields = null } = {}) {
  draft.name = name;
  draft.title = title;
  draft.color = color || 'teal';
  draft.fields = fields && fields.length
    ? fields.map((f) => ({ label: f.label || '', hint: f.hint || '' }))
    : [{ label: '', hint: '' }, { label: '', hint: '' }];
}
function openCreateBlock() {
  editingId.value = null;
  resetDraft();
  editorOpen.value = true;
  nextTick(() => nameInput.value?.focus());
}
function openEditBlock(tpl) {
  editingId.value = tpl.id;
  resetDraft(tpl);
  editorOpen.value = true;
  nextTick(() => nameInput.value?.focus());
}
function closeEditor() { editorOpen.value = false; }
function addField() { draft.fields.push({ label: '', hint: '' }); }
function removeField(index) {
  draft.fields.splice(index, 1);
  if (!draft.fields.length) draft.fields.push({ label: '', hint: '' });
}
function focusFirstField() {
  const el = Array.isArray(firstFieldInput.value) ? firstFieldInput.value[0] : firstFieldInput.value;
  el?.focus?.();
}
function cleanFields() {
  return draft.fields
    .map((f) => ({ label: (f.label || '').trim(), hint: (f.hint || '').trim() }))
    .filter((f) => f.label || f.hint);
}
async function saveBlock() {
  const name = draft.name.trim();
  if (!name || saving.value) return;
  saving.value = true;
  const payload = { name, title: draft.title.trim(), color: draft.color || 'teal', fields: cleanFields() };
  try {
    if (editingId.value) {
      await notesStore.updateBlockTemplate(editingId.value, payload);
      notify({ type: 'success', title: 'Schnellblock aktualisiert', message: `„${name}" wurde gespeichert.` });
    } else {
      await notesStore.createBlockTemplate(payload);
      notify({ type: 'success', title: 'Schnellblock erstellt', message: `„${name}" steht jetzt im /-Menü bereit.` });
    }
    editorOpen.value = false;
  } catch (error) {
    notifyError(error, 'Schnellblock konnte nicht gespeichert werden.');
  } finally {
    saving.value = false;
  }
}

/* ── Startnotizen ───────────────────────────────────────────────────────── */
async function startNote(tpl) {
  if (busy.value || !tpl?.id) return;
  busy.value = true;
  try {
    const note = await notesStore.createFromTemplate(tpl.id);
    emit('changed');
    emit('open-note', note.id, { cursorPosition: 'end' });
  } catch (error) {
    notifyError(error, 'Aus der Startnotiz konnte keine Notiz erstellt werden.');
  } finally {
    busy.value = false;
  }
}
function editStartnotiz(tpl) {
  if (!tpl?.id) return;
  emit('open-note', tpl.id);
}
async function createStartnotiz() {
  if (busy.value) return;
  busy.value = true;
  try {
    const note = await apiCreateNote({ is_template: true, title: 'Neue Startnotiz' });
    await notesStore.fetchTemplates();
    notify({ type: 'success', title: 'Startnotiz angelegt', message: 'Öffne sie und baue das Gerüst auf.' });
    emit('changed');
    emit('open-note', note.id, { cursorPosition: 'end' });
  } catch (error) {
    notifyError(error, 'Startnotiz konnte nicht angelegt werden.');
  } finally {
    busy.value = false;
  }
}

/* ── Löschen (beide Arten, mit Bestätigung) ─────────────────────────────── */
const confirm = ref({ open: false, title: '', subtitle: '', primaryText: 'Löschen', onPrimary: () => {} });
function openConfirm(config) { confirm.value = { open: true, primaryText: 'Löschen', ...config }; }
function closeConfirm() { confirm.value = { ...confirm.value, open: false }; }

function confirmDeleteBlock(tpl) {
  const label = tpl.name || tpl.title || 'diesen Schnellblock';
  openConfirm({
    title: 'Schnellblock löschen?',
    subtitle: `„${label}" wird entfernt.`,
    onPrimary: () => doDeleteBlock(tpl),
  });
}
async function doDeleteBlock(tpl) {
  if (busy.value) return;
  busy.value = true;
  try {
    await notesStore.deleteBlockTemplate(tpl.id);
    closeConfirm();
    notify({ type: 'success', title: 'Schnellblock gelöscht', message: `„${tpl.name || tpl.title}" wurde entfernt.` });
  } catch (error) {
    notifyError(error, 'Schnellblock konnte nicht gelöscht werden.');
  } finally {
    busy.value = false;
  }
}

function confirmDeleteStart(tpl) {
  const label = tpl.title?.trim() || 'diese Startnotiz';
  openConfirm({
    title: 'Startnotiz löschen?',
    subtitle: `„${label}" wird unwiderruflich gelöscht.`,
    primaryText: 'Endgültig löschen',
    onPrimary: () => doDeleteStart(tpl),
  });
}
async function doDeleteStart(tpl) {
  if (busy.value) return;
  busy.value = true;
  try {
    await notesStore.deletePermanently(tpl.id);
    await notesStore.fetchTemplates();
    closeConfirm();
    emit('changed');
    notify({ type: 'success', title: 'Startnotiz gelöscht', message: `„${tpl.title?.trim() || 'Ohne Titel'}" wurde entfernt.` });
  } catch (error) {
    notifyError(error, 'Startnotiz konnte nicht gelöscht werden.');
  } finally {
    busy.value = false;
  }
}
</script>

<style scoped>
.vm { padding: 4px 0 6px; }

.vm__sections { display: flex; flex-direction: column; gap: 26px; }

/* Abschnittskopf */
.vm__sechead {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 14px;
}
.vm__sectitle { display: flex; align-items: center; gap: 9px; }
.vm__secicon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  color: var(--pm-muted, #535e62);
  background: color-mix(in srgb, var(--pm-text, #0e181b) 7%, transparent);
}
.vm__secicon--block { color: var(--pm-accent, #006b75); background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent); }
.vm__secname { margin: 0; font-size: 1.02rem; font-weight: 620; color: var(--pm-text, #0e181b); }
.vm__count {
  min-width: 20px;
  padding: 1px 7px;
  border-radius: 20px;
  font-size: 0.74rem;
  font-weight: 620;
  text-align: center;
  color: var(--pm-muted, #535e62);
  background: color-mix(in srgb, var(--pm-text, #0e181b) 7%, transparent);
}
.vm__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
@media (max-width: 1080px) { .vm__grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 820px) { .vm__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }


/* Geisterkarten (echoen das neue Karten-Layout) */
.vg {
  --vg-accent: var(--pm-muted, #8a969b);
  display: flex;
  flex-direction: column;
  border: 1px dashed color-mix(in srgb, var(--vg-accent) 30%, var(--pm-divider, #d8dfe1));
  border-radius: 12px;
  background: var(--pm-content-surface, #fff);
  overflow: hidden;
  opacity: 0.75;
}
.vg--start { --vg-accent: color-mix(in srgb, var(--pm-text, #0e181b) 30%, var(--pm-divider, #d8dfe1)); }
.vg__preview {
  height: 108px;
  padding: 22px 16px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 10px;
  background: color-mix(in srgb, var(--vg-accent) 8%, var(--pm-content-surface, #fff));
}
.vg__preview--page { gap: 8px; }
.vg__row { display: flex; align-items: center; gap: 9px; }
.vg__pill { width: 30%; height: 7px; border-radius: 4px; background: color-mix(in srgb, var(--vg-accent) 34%, transparent); flex: none; }
.vg__line { flex: 1; height: 7px; border-radius: 4px; background: color-mix(in srgb, var(--vg-accent) 16%, transparent); }
.vg__pline { height: 6px; border-radius: 3px; background: color-mix(in srgb, var(--pm-text, #0e181b) 12%, transparent); }
.vg__meta { display: flex; align-items: center; gap: 9px; padding: 11px 13px; border-top: 1px dashed color-mix(in srgb, var(--vg-accent) 24%, var(--pm-divider, #d8dfe1)); }
.vg__chip { width: 28px; height: 28px; flex: none; border-radius: 8px; background: color-mix(in srgb, var(--vg-accent) 16%, transparent); }
.vg__name { height: 9px; width: 58%; border-radius: 4px; background: color-mix(in srgb, var(--pm-text, #0e181b) 11%, transparent); }

/* Schnellblock-Editor (Modal) */
.vm-modal {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(10, 20, 24, 0.42);
}
.vm-modal__card {
  width: min(560px, 100%);
  max-height: 88vh;
  overflow-y: auto;
  background: var(--pm-content-surface, #fff);
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 16px;
  box-shadow: 0 20px 52px rgba(15, 23, 42, 0.3);
  padding: 22px 24px;
}
.vm-modal__title { display: flex; align-items: center; gap: 8px; font-size: 1.04rem; font-weight: 600; color: var(--pm-text, #0e181b); margin-bottom: 16px; }
.vm-modal__two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 480px) { .vm-modal__two { grid-template-columns: 1fr; } }
.vm-modal__row { display: block; margin-bottom: 14px; }
.vm-modal__label { display: block; font-size: 0.76rem; font-weight: 600; color: var(--pm-muted, #535e62); margin-bottom: 6px; }
.vm-modal__input,
.vm-field__input {
  width: 100%;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 8px;
  padding: 8px 11px;
  font: inherit;
  font-size: 0.88rem;
  background: var(--pm-app-surface, #fff);
  color: var(--pm-text, #0e181b);
}
.vm-modal__input:focus,
.vm-field__input:focus { outline: none; border-color: var(--pm-accent, #006b75); box-shadow: 0 0 0 3px color-mix(in srgb, var(--pm-accent, #006b75) 16%, transparent); }
.vm-modal__colors { display: flex; gap: 8px; }
.vm-modal__swatch {
  width: 22px; height: 22px; padding: 0; border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--sw) 55%, transparent);
  background: var(--sw); cursor: pointer;
  transition: transform 100ms ease, box-shadow 100ms ease;
}
.vm-modal__swatch:hover { transform: scale(1.12); }
.vm-modal__swatch.is-active { box-shadow: 0 0 0 2px var(--pm-content-surface, #fff), 0 0 0 3px var(--sw); }
.vm-modal__fields { --c: var(--pm-accent, #006b75); margin: 2px 0 8px; }
.vm-modal__fieldshead { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
.vm-modal__fieldshint { font-size: 0.72rem; color: var(--pm-muted, #535e62); }
.vm-field { display: grid; grid-template-columns: 3px 1fr 1fr auto; gap: 7px; margin-bottom: 7px; align-items: center; }
.vm-field__bar { align-self: stretch; border-radius: 3px; background: color-mix(in srgb, var(--c) 55%, transparent); }
.vm-field__del {
  display: grid; place-items: center;
  border: 0; background: transparent; color: var(--pm-muted, #535e62);
  width: 30px; height: 30px; border-radius: 7px; cursor: pointer;
  transition: color 120ms ease, background 120ms ease;
}
.vm-field__del:hover { color: var(--pm-danger, #c0392b); background: color-mix(in srgb, var(--pm-danger, #c0392b) 10%, transparent); }
.vm-addfield {
  display: inline-flex; align-items: center; gap: 4px;
  border: 1px dashed var(--pm-divider, #d8dfe1); background: transparent;
  color: var(--pm-muted, #535e62); border-radius: 8px; padding: 6px 11px;
  font: inherit; font-size: 0.8rem; cursor: pointer; margin-top: 3px;
  transition: border-color 120ms ease, color 120ms ease;
}
.vm-addfield:hover { border-color: var(--pm-accent, #006b75); color: var(--pm-accent-strong, #00555f); }
.vm-modal__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
.vm-btn {
  border: 1px solid var(--pm-divider, #d8dfe1); background: var(--pm-app-surface, #fff);
  color: var(--pm-text, #0e181b); border-radius: 9px; padding: 9px 16px;
  font: inherit; font-size: 0.85rem; font-weight: 500; cursor: pointer;
  transition: background 120ms ease;
}
.vm-btn:hover { background: color-mix(in srgb, var(--pm-text, #0e181b) 5%, var(--pm-app-surface, #fff)); }
.vm-btn--primary { background: var(--pm-accent, #006b75); color: var(--pm-accent-contrast, #fff); border-color: var(--pm-accent, #006b75); }
.vm-btn--primary:hover { background: var(--pm-accent-strong, #00555f); }
.vm-btn--primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
