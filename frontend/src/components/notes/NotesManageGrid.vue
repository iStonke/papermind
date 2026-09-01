<!--
  NotesManageGrid — großflächige Verwaltungsfläche des Notizbereichs.
  Rendert die Notizen als mehrspaltiges Kartenraster (statt schmaler Liste)
  mit kartenbezogenen Aktionsmenüs und Inline-Umbenennen. Die Umschaltung
  zwischen Notizen und Vorlagen liegt in der Kopfzeile von NotesWorkspace. Wird
  dort in einer eigenständigen, vollbreiten Verwaltungsfläche gezeigt.
-->
<template>
  <div class="nmg">
    <div class="nmg__body">
      <!-- Inhalt -->
      <div class="nmg__scroll">
        <Vorlagenmappe
          v-if="facet === 'templates'"
          class="nmg__vorlagenmappe"
          @open-note="(id, opts) => $emit('open-note', id, opts)"
          @changed="$emit('changed')"
        />

        <div v-if="facet === 'notes' && visibleItems.length" class="nmg__toolbar">
          <v-menu location="bottom start" :offset="4">
            <template #activator="{ props: sortProps }">
              <button type="button" class="nmg__sort-btn" v-bind="sortProps" :disabled="busy">
                <v-icon size="15">mdi-sort</v-icon>
                <span class="nmg__sort-label">{{ sortLabel }}</span>
                <v-icon size="15">mdi-chevron-down</v-icon>
              </button>
            </template>
            <v-list density="compact" min-width="212" class="nmg__sort-list">
              <v-list-item
                v-for="opt in NOTE_SORT_OPTIONS"
                :key="opt.value"
                :title="opt.label"
                :active="sortMode === opt.value"
                @click="sortMode = opt.value"
              >
                <template v-if="sortMode === opt.value" #append>
                  <v-icon size="16">mdi-check</v-icon>
                </template>
              </v-list-item>
            </v-list>
          </v-menu>
        </div>

        <div
          v-if="facet === 'notes' && !visibleItems.length && normalizedQuery"
          key="empty-search"
          class="nmg__empty"
        >
          <PmEmptyState
            :icon="emptyState.icon"
            :title="emptyState.title"
            :subtitle="emptyState.subtitle"
            size="sm"
          />
        </div>

        <div
          v-else-if="facet === 'notes' && !visibleItems.length"
          key="empty-ghosts"
          class="nmg__ghost-empty"
        >
          <div class="nmg__grid nmg__ghosts">
            <div v-for="i in 7" :key="i" class="nmg-ghost" aria-hidden="true">
              <div class="nmg-ghost__preview">
                <span class="nmg-ghost__line" style="width: 88%" />
                <span class="nmg-ghost__line" style="width: 66%" />
                <span class="nmg-ghost__line" style="width: 78%" />
              </div>
              <div class="nmg-ghost__meta"><span class="nmg-ghost__chip" /><span class="nmg-ghost__name" /></div>
            </div>
            <GhostAddCard
              title="Noch keine Notiz"
              subtitle="Neue Notiz anlegen"
              @click="$emit('create-note')"
            />
          </div>
        </div>

        <div v-else-if="facet === 'notes'" key="items" class="nmg__groups">
          <section v-for="group in groupedItems" :key="group.key" class="nmg__group">
            <h3 class="nmg__group-heading">{{ group.label }}</h3>
            <ul class="nmg__grid">
              <li
                v-for="note in group.notes"
                :key="note.id"
                class="nmg-card"
                :class="{ 'is-editing': editingId === note.id }"
                role="button"
                tabindex="0"
                @click="onCardClick(note)"
                @keydown.enter="onCardClick(note)"
              >
                <div class="nmg-card__preview">
                  <p class="nmg-card__snippet">{{ snippet(note) }}</p>
                  <span
                    v-if="note.link_count > 0"
                    class="nmg-card__links"
                    :title="`${note.link_count} Verknüpfung${note.link_count === 1 ? '' : 'en'}`"
                  >
                    <v-icon size="12">mdi-link-variant</v-icon>{{ note.link_count }}
                  </span>
                  <div class="nmg-card__actions" @click.stop>
                    <button type="button" class="nmg-card__act" title="Umbenennen" aria-label="Umbenennen" @click="startRename(note)">
                      <v-icon size="15">mdi-pencil-outline</v-icon>
                    </button>
                    <button type="button" class="nmg-card__act" title="Als Vorlage speichern" aria-label="Als Vorlage speichern" @click="saveNoteAsTemplate(note)">
                      <v-icon size="15">mdi-content-copy</v-icon>
                    </button>
                    <button type="button" class="nmg-card__act nmg-card__act--danger" title="In Papierkorb" aria-label="In Papierkorb" @click="trashNote(note)">
                      <v-icon size="15">mdi-trash-can-outline</v-icon>
                    </button>
                  </div>
                </div>

                <div class="nmg-card__meta">
                  <span class="nmg-card__chip" aria-hidden="true"><v-icon size="16">mdi-note-outline</v-icon></span>
                  <input
                    v-if="editingId === note.id"
                    ref="titleInputRef"
                    v-model="editingTitle"
                    class="nmg-card__title-input"
                    type="text"
                    maxlength="500"
                    placeholder="Titel …"
                    @click.stop
                    @keydown.enter.prevent.stop="commitRename(note)"
                    @keydown.esc.prevent.stop="cancelRename"
                    @blur="commitRename(note)"
                  />
                  <span
                    v-else
                    class="nmg-card__title"
                    :class="{ 'is-untitled': !note.title?.trim() }"
                  >{{ note.title?.trim() || 'Ohne Titel' }}</span>
                </div>

                <div class="nmg-card__foot" @click.stop>
                  <NoteTagBar
                    class="nmg-card__tags"
                    :tag-ids="(note.tags || []).map((t) => t.id)"
                    :all-tags="allTagsForCard(note)"
                    compact
                    :create-tag-by-name="tagStore.ensureTagIdByName"
                    :load-tags="tagStore.fetchTags"
                    @update:tag-ids="(ids) => applyCardTags(note, ids)"
                  />
                  <span class="nmg-card__date">{{ formatDate(note.updated_at) }}</span>
                </div>
              </li>
            </ul>
          </section>
        </div>
      </div>

      <button
        v-if="facet === 'notes' && !tagSidebarOpen"
        type="button"
        class="nmg__tag-sidebar-toggle"
        aria-label="Tag-Filter öffnen"
        @click="tagSidebarOpen = true"
      >
        <v-icon size="18">mdi-tag</v-icon>
      </button>

      <aside
        v-if="facet === 'notes'"
        class="nmg__tag-sidebar"
        :class="{ 'is-open': tagSidebarOpen }"
        aria-label="Notizen nach Tags filtern"
      >
        <div class="nmg__tag-sidebar-head">
          <h2 class="nmg__tag-sidebar-title">Tags</h2>
          <div class="nmg__tag-sidebar-actions">
            <button
              type="button"
              class="nmg__tag-sidebar-action nmg__tag-sidebar-close"
              aria-label="Tag-Filter schließen"
              @click="tagSidebarOpen = false"
            >
              <v-icon size="18">mdi-close</v-icon>
            </button>
          </div>
        </div>

        <div class="nmg__tag-cloud" role="group" aria-label="Verwendete Tags">
          <div class="nmg__tag-cloud-items">
            <button
              type="button"
              class="nmg__tag-cloud-chip"
              :class="{ 'is-active': !activeTagId }"
              :aria-pressed="String(!activeTagId)"
              @click="activeTagId = null"
            >
              <span class="nmg__tag-cloud-name">Alle Notizen</span>
              <span class="nmg__tag-cloud-count">{{ allNotes.length }}</span>
            </button>

            <button
              v-for="tag in tagCloudItems"
              :key="tag.id"
              type="button"
              class="nmg__tag-cloud-chip"
              :class="{ 'is-active': activeTagId === tag.id }"
              :aria-pressed="String(activeTagId === tag.id)"
              @click="toggleTagFilter(tag.id)"
            >
              <span class="nmg__tag-cloud-name">{{ tag.name }}</span>
              <span class="nmg__tag-cloud-count">{{ tag.count }}</span>
            </button>
          </div>

          <div v-if="!tagCloudItems.length" class="nmg__tag-cloud-empty">
            <span class="nmg__tag-cloud-empty-glyph" aria-hidden="true"><v-icon size="24">mdi-tag-outline</v-icon></span>
            <p class="nmg__tag-cloud-empty-title">Noch keine Tags</p>
            <p class="nmg__tag-cloud-empty-text">Weise einer Notiz ein Tag zu, dann kannst du hier danach filtern.</p>
          </div>
        </div>
      </aside>
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
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import DestructiveDialog from '../DestructiveDialog.vue';
import PmEmptyState from '../PmEmptyState.vue';
import { patchNote } from '../../api/notes.js';
import { useNotesStore } from '../../stores/notes.js';
import { useTagStore } from '../../stores/tags.js';
import { useSettingsStore } from '../../stores/settings.js';
import { notifyError, useNotifications } from '../../stores/notifications.js';
import NoteTagBar from './NoteTagBar.vue';
import Vorlagenmappe from './Vorlagenmappe.vue';
import GhostAddCard from './GhostAddCard.vue';

const props = defineProps({
  facet: { type: String, default: 'notes' },
  searchQuery: { type: String, default: '' },
  searchScope: { type: String, default: 'all' },
});

const emit = defineEmits(['open-note', 'changed', 'create-note']);

const notesStore = useNotesStore();
const tagStore = useTagStore();
const settingsStore = useSettingsStore();
const { notify } = useNotifications();

const loadingTemplates = ref(false);
const busy = ref(false);
const activeTagId = ref(null);
const tagSidebarOpen = ref(false);

// Sortierung – identisch zur Listenansicht (gleiche Optionen, gleicher
// Default aus ui.notes_sort_order); sitzungslokal wie dort.
const NOTE_SORT_OPTIONS = [
  { value: 'updated', label: 'Zuletzt bearbeitet' },
  { value: 'created', label: 'Erstellungsdatum' },
  { value: 'title', label: 'Titel (A–Z)' },
];
function normalizeSortMode(value) {
  return NOTE_SORT_OPTIONS.some((o) => o.value === value) ? value : 'updated';
}
const sortMode = ref(normalizeSortMode(settingsStore.settingsDraft.ui.notes_sort_order));
watch(
  () => settingsStore.settingsDraft.ui.notes_sort_order,
  (order) => { sortMode.value = normalizeSortMode(order); },
);
const sortLabel = computed(
  () => NOTE_SORT_OPTIONS.find((o) => o.value === sortMode.value)?.label || 'Sortierung',
);
function sortTimestamp(value) {
  const t = value ? new Date(value).getTime() : 0;
  return Number.isFinite(t) ? t : 0;
}
function sortItems(items) {
  const copy = [...items];
  if (sortMode.value === 'title') {
    return copy.sort((a, b) => String(a.title || '').localeCompare(String(b.title || ''), 'de-DE'));
  }
  if (sortMode.value === 'created') {
    return copy.sort((a, b) => sortTimestamp(b.created_at || b.updated_at) - sortTimestamp(a.created_at || a.updated_at));
  }
  return copy.sort((a, b) => sortTimestamp(b.updated_at) - sortTimestamp(a.updated_at));
}

const editingId = ref(null);
const editingTitle = ref('');
const titleInputRef = ref(null);

const confirm = ref({ open: false, title: '', subtitle: '', primaryText: '', onPrimary: () => {} });

// Bewusst Kopien: Der Store mutiert `notes` teils in-place (z. B. unshift beim
// Anlegen). Ein Spread liest Länge und alle Indizes und stellt so die tiefe
// Reaktivität her – sonst bliebe der Computed an der unveränderten Referenz hängen.
const allNotes = computed(() => [...notesStore.notes]);
const templateNotes = computed(() => [...notesStore.templates]);

const facet = computed(() => (props.facet === 'templates' ? 'templates' : 'notes'));

const facetItems = computed(() => {
  if (facet.value === 'templates') return templateNotes.value;
  return allNotes.value;
});

const normalizedQuery = computed(() => String(props.searchQuery || '').trim().toLocaleLowerCase('de-DE'));

const visibleItems = computed(() => {
  let items = facetItems.value;
  // Tag-Filter (nur Notizen; Vorlagen tragen im Verwaltungsfluss keine Tags).
  if (facet.value === 'notes' && activeTagId.value) {
    items = items.filter((n) => (n.tags || []).some((t) => t.id === activeTagId.value));
  }
  const q = normalizedQuery.value;
  if (q) {
    const terms = q.split(/\s+/).filter(Boolean);
    const scope = props.searchScope;
    items = items.filter((n) => {
      const title = String(n.title || '').toLocaleLowerCase('de-DE');
      const body = String(n.preview || '').toLocaleLowerCase('de-DE');
      const hay = scope === 'title' ? title : scope === 'body' ? body : `${title} ${body}`;
      return terms.every((t) => hay.includes(t));
    });
  }
  return sortItems(items);
});

// Zeitraum-Gruppierung (immer aktiv). Buckets in fester chronologischer
// Reihenfolge; die Sortierung wirkt innerhalb jeder Gruppe. Das Datumsfeld
// folgt der Sortierung (Erstellungsdatum bzw. sonst Bearbeitungsdatum).
const GROUP_ORDER = ['today', 'yesterday', 'week', 'month', 'older'];
const GROUP_LABELS = {
  today: 'Heute',
  yesterday: 'Gestern',
  week: 'Diese Woche',
  month: 'Diesen Monat',
  older: 'Älter',
};
function startOfDay(value) {
  const d = new Date(value);
  d.setHours(0, 0, 0, 0);
  return d;
}
function groupBucket(note) {
  const raw = (sortMode.value === 'created' ? note.created_at : note.updated_at) || note.updated_at;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return 'older';
  const now = new Date();
  const diffDays = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
  if (diffDays <= 0) return 'today';
  if (diffDays === 1) return 'yesterday';
  if (diffDays <= 6) return 'week';
  if (d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth()) return 'month';
  return 'older';
}
const groupedItems = computed(() => {
  const buckets = new Map();
  for (const note of visibleItems.value) {
    const key = groupBucket(note);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(note);
  }
  return GROUP_ORDER
    .filter((key) => buckets.has(key))
    .map((key) => ({ key, label: GROUP_LABELS[key], notes: buckets.get(key) }));
});

// Nur tatsächlich vergebene Tags (mit Häufigkeit) als Filter-Wolke anbieten.
const usedTags = computed(() => {
  if (facet.value !== 'notes') return [];
  const counts = new Map();
  for (const note of allNotes.value) {
    for (const tag of note.tags || []) {
      const entry = counts.get(tag.id) || { id: tag.id, name: tag.name, count: 0 };
      entry.count += 1;
      counts.set(tag.id, entry);
    }
  }
  return [...counts.values()].sort((a, b) => a.name.localeCompare(b.name, 'de-DE'));
});

const tagCloudItems = computed(() => usedTags.value);

// allTags-Pool für den Karten-Picker: alle Owner-Tags + die der Notiz (Namen).
function allTagsForCard(note) {
  const map = new Map();
  for (const t of tagStore.tags || []) map.set(String(t.id), { id: String(t.id), name: t.name });
  for (const t of note.tags || []) if (!map.has(String(t.id))) map.set(String(t.id), { id: String(t.id), name: t.name });
  return [...map.values()];
}

function toggleTagFilter(tagId) {
  activeTagId.value = activeTagId.value === tagId ? null : tagId;
}

async function applyCardTags(note, tagIds) {
  try {
    const updated = await notesStore.setTags(note.id, { tagIds });
    note.tags = updated.tags || [];
    // Gefiltertes Tag entfernt? Filter zurücksetzen, damit die Karte nicht springt.
    if (activeTagId.value && !(note.tags || []).some((t) => t.id === activeTagId.value)) {
      // nur zurücksetzen, wenn keine Notiz mehr das Tag trägt
      if (!allNotes.value.some((n) => (n.tags || []).some((t) => t.id === activeTagId.value))) {
        activeTagId.value = null;
      }
    }
  } catch (error) {
    notifyError(error, 'Tags konnten nicht gespeichert werden.');
  }
}

const isLoading = computed(() => facet.value === 'templates' && loadingTemplates.value);

const emptyState = computed(() => {
  if (normalizedQuery.value) {
    return { icon: 'mdi-note-search-outline', title: 'Keine Treffer', subtitle: 'Passe den Suchbegriff an oder leere die globale Suche.' };
  }
  if (facet.value === 'templates') {
    return { icon: 'mdi-file-document-multiple-outline', title: 'Keine Vorlagen', subtitle: 'Speichere eine Notiz als Vorlage, um sie hier zu verwalten.' };
  }
  return { icon: 'mdi-note-outline', title: 'Noch keine Notizen', subtitle: 'Halte Gedanken und Fundstellen an einem Ort fest.' };
});

onMounted(async () => {
  tagStore.fetchTags().catch(() => {});
  if (notesStore.templatesLoaded) return;
  loadingTemplates.value = true;
  try {
    await notesStore.ensureTemplatesLoaded();
  } finally {
    loadingTemplates.value = false;
  }
});

watch(facet, () => {
  cancelRename();
  closeConfirm();
  activeTagId.value = null;
  tagSidebarOpen.value = false;
});

watch(usedTags, (tags) => {
  if (activeTagId.value && !tags.some((tag) => tag.id === activeTagId.value)) {
    activeTagId.value = null;
  }
});

function onCardClick(note) {
  if (facet.value === 'notes') emit('open-note', note.id);
}

// --- Inline-Umbenennen -----------------------------------------------------
function startRename(note) {
  editingId.value = note.id;
  editingTitle.value = note.title || '';
  nextTick(() => {
    const el = Array.isArray(titleInputRef.value) ? titleInputRef.value[0] : titleInputRef.value;
    el?.focus?.();
    el?.select?.();
  });
}

function cancelRename() { editingId.value = null; }

async function commitRename(note) {
  if (editingId.value !== note.id) return;
  const title = editingTitle.value.trim().slice(0, 500);
  editingId.value = null;
  if (title === (note.title || '').trim()) return;
  try {
    const updated = await patchNote(note.id, { title });
    // Das Listenobjekt ist dieselbe Referenz wie im Store → Mutation genügt.
    note.title = updated.title;
    note.updated_at = updated.updated_at;
  } catch (error) {
    notifyError(error, 'Der Titel konnte nicht gespeichert werden.');
  }
}

// --- Kartenaktionen --------------------------------------------------------
async function trashNote(note) {
  if (busy.value || !note?.id) return;
  busy.value = true;
  try {
    await notesStore.remove(note.id);
    emit('changed');
  } catch (error) {
    notifyError(error, 'Die Notiz konnte nicht in den Papierkorb verschoben werden.');
  } finally {
    busy.value = false;
  }
}

async function saveNoteAsTemplate(note) {
  if (busy.value || !note?.id) return;
  busy.value = true;
  try {
    const template = await notesStore.saveAsTemplate(note.id, { title: note.title || '' });
    const title = template.title?.trim() || 'Ohne Titel';
    notify({
      type: 'success',
      title: 'Vorlage gespeichert',
      message: `„${title}“ wurde zu deinen Vorlagen hinzugefügt.`,
      critical: true,
    });
    emit('changed');
  } catch (error) {
    notifyError(error, 'Die Vorlage konnte nicht gespeichert werden.');
  } finally {
    busy.value = false;
  }
}

async function createNoteFromTemplate(template) {
  if (busy.value || !template?.id) return;
  busy.value = true;
  try {
    const note = await notesStore.createFromTemplate(template.id);
    emit('changed');
    emit('open-note', note.id, { cursorPosition: 'end' });
  } catch (error) {
    notifyError(error, 'Aus der Vorlage konnte keine Notiz erstellt werden.');
  } finally {
    busy.value = false;
  }
}

function requestTemplateDeletion(template) {
  if (busy.value || !template?.id) return;
  const title = template.title?.trim() || 'Ohne Titel';
  openConfirm({
    title: 'Vorlage löschen?',
    subtitle: `„${title}“ wird unwiderruflich gelöscht.`,
    primaryText: 'Endgültig löschen',
    onPrimary: () => deleteTemplate(template),
  });
}

async function deleteTemplate(template) {
  if (busy.value || !template?.id) return;
  busy.value = true;
  try {
    await notesStore.deletePermanently(template.id);
    await notesStore.fetchTemplates();
    confirm.value = { ...confirm.value, open: false };
    emit('changed');
  } catch (error) {
    notifyError(error, 'Die Vorlage konnte nicht gelöscht werden.');
  } finally {
    busy.value = false;
  }
}

function openConfirm({ title, subtitle, primaryText, onPrimary }) {
  confirm.value = { open: true, title, subtitle, primaryText, onPrimary };
}

function closeConfirm() {
  if (busy.value) return;
  confirm.value = { ...confirm.value, open: false };
}

function snippet(note) {
  return note.preview?.trim().replace(/\s+/g, ' ') || 'Leer';
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const time = date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  if (date.toDateString() === now.toDateString()) return `heute ${time}`;
  if (date.toDateString() === yesterday.toDateString()) return `gestern ${time}`;
  return date.toLocaleDateString('de-DE', {
    day: 'numeric',
    month: 'short',
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: 'numeric' }),
  });
}
</script>

<style scoped>
.nmg {
  display: flex;
  width: 100%;
  flex: 1 1 auto;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

/* Raster und Filter teilen sich die Verwaltungsfläche. */
.nmg__body {
  position: relative;
  display: flex;
  width: 100%;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.nmg__tag-sidebar {
  display: flex;
  width: clamp(270px, 27vw, 320px);
  min-height: 0;
  flex: none;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid var(--pm-divider, #d8dfe1);
  background: color-mix(in srgb, var(--pm-app-surface, #fff) 96%, var(--pm-accent, #006b75));
}

.nmg__tag-sidebar-head,
.nmg__tag-sidebar-title,
.nmg__tag-sidebar-actions {
  display: flex;
  align-items: center;
}

.nmg__tag-sidebar-head {
  min-height: 49px;
  flex: 0 0 auto;
  gap: 8px;
  padding: 7px 8px 7px 12px;
}

.nmg__tag-sidebar-title {
  margin: 0;
  min-width: 0;
  flex: 1 1 auto;
  padding: 0 4px;
  color: var(--pm-text, #0f172a);
  font-size: 0.82rem;
  font-weight: 680;
  line-height: 1.3;
  text-align: left;
}

.nmg__tag-sidebar-actions {
  flex: 0 0 auto;
  gap: 2px;
}

.nmg__tag-sidebar-action,
.nmg__tag-sidebar-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  color: var(--pm-muted, #64748b);
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease, background 120ms ease;
}

.nmg__tag-sidebar-action {
  width: 30px;
  height: 30px;
  border-radius: 8px;
}

.nmg__tag-sidebar-action:hover,
.nmg__tag-sidebar-action:focus-visible,
.nmg__tag-sidebar-toggle:hover,
.nmg__tag-sidebar-toggle:focus-visible {
  background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 52%, transparent);
  color: var(--pm-text, #0e181b);
  outline: none;
}

.nmg__tag-sidebar-close,
.nmg__tag-sidebar-toggle {
  display: none;
}

.nmg__tag-cloud {
  --pm-detail-chip-bg: var(--pm-chip-bg, rgba(var(--v-theme-on-surface), 0.06));
  --pm-detail-chip-border: color-mix(in srgb, var(--pm-chip-text, var(--pm-text)) 14%, transparent);
  --pm-detail-chip-count: var(--pm-chip-count, var(--pm-muted));
  display: flex;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding: 4px 16px 18px;
}

/* Einheitliche Filter-Chips */
.nmg__tag-cloud-items {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  align-items: center;
  gap: 7px;
}
.nmg__tag-cloud-chip {
  display: inline-flex;
  height: 26px;
  width: auto;
  max-width: min(220px, 100%);
  min-width: 0;
  flex: 0 1 auto;
  align-items: center;
  gap: 5px;
  padding: 0 7px 0 11px;
  border: 1px solid var(--pm-detail-chip-border);
  border-radius: 15px;
  background: var(--pm-detail-chip-bg);
  box-shadow: none;
  color: rgba(var(--v-theme-on-surface), 0.88);
  font-size: 12.5px;
  font-weight: 500;
  line-height: 1.2;
  text-align: left;
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease, background 120ms ease;
}
.nmg__tag-cloud-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nmg__tag-cloud-count {
  flex: none;
  min-width: 18px;
  margin-inline-start: 1px;
  padding: 0;
  border-radius: 0;
  font-size: 0.7rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-align: center;
  color: var(--pm-detail-chip-count);
  background: transparent;
}
.nmg__tag-cloud-chip:hover,
.nmg__tag-cloud-chip:focus-visible {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 30%, transparent);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 7%, var(--pm-chip-bg, #e7eef0));
  color: var(--pm-text, #0e181b);
  outline: none;
}
.nmg__tag-cloud-chip.is-active {
  border-color: var(--pm-accent, #006b75);
  background: var(--pm-accent, #006b75);
  color: var(--pm-on-accent, #fff);
  font-weight: 600;
}
.nmg__tag-cloud-chip.is-active .nmg__tag-cloud-count {
  color: var(--pm-on-accent, #fff);
  background: transparent;
}

/* Leerzustand */
.nmg__tag-cloud-empty {
  display: flex;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 2px;
  padding: 24px 12px;
}
.nmg__tag-cloud-empty-glyph {
  margin-bottom: 7px;
  color: var(--pm-muted, #64748b);
  opacity: 0.52;
}
.nmg__tag-cloud-empty-title { margin: 0; font-size: 0.82rem; font-weight: 620; color: var(--pm-text, #0f172a); }
.nmg__tag-cloud-empty-text { margin: 0; max-width: 24ch; font-size: 0.74rem; line-height: 1.5; color: var(--pm-muted, #64748b); }

/* Inhalt */
.nmg__scroll {
  position: relative;
  display: flex;
  width: 0;
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: auto;
}

.nmg__toolbar {
  flex: none;
  display: flex;
  align-items: center;
  padding: 22px 26px 10px;
}
.nmg__sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 8px 5px 10px;
  border-radius: 8px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  background: transparent;
  color: var(--pm-text, #0f172a);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
}
.nmg__sort-btn > .v-icon:first-child { color: var(--pm-muted, #64748b); }
.nmg__sort-btn:hover:not(:disabled) {
  background: var(--pm-row-hover, rgba(0, 107, 117, 0.05));
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 40%, transparent);
}
.nmg__sort-btn:disabled { opacity: 0.5; cursor: default; }
.nmg__sort-label { color: var(--pm-muted, #64748b); }
.nmg__sort-list {
  padding: 5px;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 76%, transparent);
  border-radius: 12px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.14);
}
@media (prefers-reduced-motion: reduce) {
  .nmg__sort-btn { transition: none; }
}

.nmg__state {
  display: flex;
  min-height: 220px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--pm-muted);
  font-size: 0.84rem;
}

.nmg__empty {
  display: flex;
  flex: 1 1 auto;
  width: 100%;
  height: 100%;
  min-height: 0;
  align-items: center;
  justify-content: center;
}

/* Vorlagen-Facet: die Vorlagenmappe füllt den Scrollbereich selbst. */
.nmg__vorlagenmappe { flex: none; padding: 22px 26px 28px; }

.nmg__groups {
  padding: 2px 26px 28px;
}

.nmg__group + .nmg__group {
  margin-top: 22px;
}

.nmg__group-heading {
  margin: 0 0 11px;
  color: var(--pm-muted, #64748b);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.nmg__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(258px, 1fr));
  align-content: start;
  gap: 16px;
  margin: 0;
  padding: 0;
  list-style: none;
}

/* ── Notiz-Karten (grafisch, wie Vorlagenmappe) ─────────────────────────── */
.nmg-card {
  --nmg-accent: var(--pm-accent, #006b75);
  position: relative;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 12px;
  background: var(--pm-content-surface, #fff);
  overflow: hidden;
  cursor: pointer;
  transition: transform 130ms cubic-bezier(0.2, 0, 0, 1), box-shadow 130ms ease, border-color 130ms ease;
}
.nmg-card:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--nmg-accent) 38%, var(--pm-divider, #d8dfe1));
  box-shadow: 0 8px 22px color-mix(in srgb, var(--nmg-accent) 18%, transparent);
}
.nmg-card:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--pm-content-surface, #fff), 0 0 0 4px color-mix(in srgb, var(--nmg-accent) 55%, transparent);
}
.nmg-card.is-editing { cursor: default; }

.nmg-card__preview {
  position: relative;
  height: 112px;
  padding: 13px 15px;
  overflow: hidden;
  background: color-mix(in srgb, var(--pm-text, #0e181b) 3.5%, var(--pm-content-surface, #fff));
}
.nmg-card__snippet {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--pm-muted, #535e62);
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.nmg-card__links {
  position: absolute;
  bottom: 9px;
  right: 12px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 8px 1px 6px;
  border-radius: 20px;
  font-size: 0.72rem;
  color: var(--pm-muted, #535e62);
  background: color-mix(in srgb, var(--pm-text, #0e181b) 6%, var(--pm-content-surface, #fff));
}

.nmg-card__actions {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 3px;
  padding: 3px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 80%, transparent);
  backdrop-filter: blur(3px);
  opacity: 0;
  transform: translateY(-2px);
  pointer-events: none;
  transition: opacity 120ms ease, transform 120ms ease;
}
.nmg-card:hover .nmg-card__actions,
.nmg-card:focus-within .nmg-card__actions { opacity: 1; transform: none; pointer-events: auto; }
.nmg-card__act {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  transition: color 120ms ease, background 120ms ease;
}
.nmg-card__act:hover { background: color-mix(in srgb, var(--pm-text, #0e181b) 8%, transparent); color: var(--pm-text, #0e181b); }
.nmg-card__act--danger:hover { color: var(--pm-danger, #c0392b); background: color-mix(in srgb, var(--pm-danger, #c0392b) 12%, transparent); }

.nmg-card__meta {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 13px 5px;
}
.nmg-card__chip {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  flex: none;
  border-radius: 8px;
  color: var(--nmg-accent);
  background: color-mix(in srgb, var(--nmg-accent) 13%, transparent);
}
.nmg-card__title {
  min-width: 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--pm-text, #0e181b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nmg-card__title.is-untitled { color: var(--pm-muted, #8a969b); font-style: italic; font-weight: 500; }
.nmg-card__title-input {
  min-width: 0;
  flex: 1;
  border: 1px solid var(--pm-accent, #006b75);
  border-radius: 7px;
  padding: 5px 8px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  background: var(--pm-app-surface, #fff);
  color: var(--pm-text, #0e181b);
  outline: none;
}

.nmg-card__foot {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 13px 11px;
}
.nmg-card__tags { flex: 1; min-width: 0; }
.nmg-card__date {
  flex: none;
  font-size: 0.72rem;
  color: var(--pm-muted, #8a969b);
  font-variant-numeric: tabular-nums;
}

@media (prefers-reduced-motion: reduce) {
  .nmg-card, .nmg-card__actions { transition: none; }
  .nmg-card:hover { transform: none; }
}

/* ── Leerzustand: Geisterkarten (wie Vorlagenmappe) ─────────────────────── */
.nmg__ghost-empty {
  flex: none;
  padding: 24px 26px 28px;
}
.nmg-ghost {
  display: flex;
  flex-direction: column;
  border: 1px dashed color-mix(in srgb, var(--pm-text, #0e181b) 12%, var(--pm-divider, #d8dfe1));
  border-radius: 12px;
  background: var(--pm-content-surface, #fff);
  overflow: hidden;
  opacity: 0.7;
}
.nmg-ghost__preview {
  height: 112px;
  padding: 18px 16px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 9px;
  background: color-mix(in srgb, var(--pm-text, #0e181b) 3.5%, var(--pm-content-surface, #fff));
}
.nmg-ghost__line { height: 7px; border-radius: 4px; background: color-mix(in srgb, var(--pm-text, #0e181b) 11%, transparent); }
.nmg-ghost__line:nth-child(2) { opacity: 0.72; }
.nmg-ghost__line:nth-child(3) { opacity: 0.85; }
.nmg-ghost__meta {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 13px;
  border-top: 1px dashed color-mix(in srgb, var(--pm-text, #0e181b) 10%, var(--pm-divider, #d8dfe1));
}
.nmg-ghost__chip { width: 28px; height: 28px; flex: none; border-radius: 8px; background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent); }
.nmg-ghost__name { height: 9px; width: 58%; border-radius: 4px; background: color-mix(in srgb, var(--pm-text, #0e181b) 11%, transparent); }

@media (max-width: 760px) {
  .nmg__tag-sidebar {
    position: absolute;
    z-index: 8;
    top: 0;
    right: 0;
    bottom: 0;
    width: clamp(270px, 88vw, 320px);
    transform: translateX(calc(100% + 36px));
    transition: transform 220ms var(--pm-easing-decel, cubic-bezier(0.16, 1, 0.3, 1));
  }

  .nmg__tag-sidebar.is-open {
    transform: translateX(0);
  }

  .nmg__tag-sidebar-close {
    display: inline-flex;
  }

  .nmg__tag-sidebar-toggle {
    position: absolute;
    z-index: 7;
    top: 12px;
    right: 12px;
    display: inline-flex;
    width: 38px;
    height: 38px;
    border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 80%, transparent);
    border-radius: 11px;
    background: var(--pm-app-surface-raised, #fff);
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    color: var(--pm-accent, #006b75);
  }
}

@media (prefers-reduced-motion: reduce) {
  .nmg__tag-sidebar,
  .nmg__tag-sidebar-action,
  .nmg__tag-sidebar-toggle,
  .nmg__tag-cloud-chip {
    transition-duration: 0ms;
  }
}

:global(.pm-no-animations) .nmg-card,
:global(.pm-no-animations) .nmg__tag-sidebar,
:global(.pm-no-animations) .nmg__tag-sidebar-action,
:global(.pm-no-animations) .nmg__tag-sidebar-toggle,
:global(.pm-no-animations) .nmg__tag-cloud-chip {
  transition-duration: 0ms;
}
</style>
