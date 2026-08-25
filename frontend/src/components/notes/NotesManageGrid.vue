<!--
  NotesManageGrid — großflächige Verwaltungsfläche des Notizbereichs.
  Rendert die Notizen als mehrspaltiges Kartenraster (statt schmaler Liste)
  mit kartenbezogenen Aktionsmenüs und Inline-Umbenennen. Die Umschaltung
  zwischen Notizen und Vorlagen liegt in der Kopfzeile von NotesWorkspace. Wird im
  „is-manage"-Zustand innerhalb des (voll ausgefahrenen) Listen-Panels gezeigt.
-->
<template>
  <div class="nmg">
    <div class="nmg__body">
      <!-- Inhalt -->
      <div class="nmg__scroll">
        <div class="nmg__toolbar">
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

        <div v-if="isLoading" key="loading" class="nmg__state" aria-live="polite">
          <v-progress-circular indeterminate color="primary" size="24" width="2" />
          <span>Wird geladen …</span>
        </div>

        <div v-else-if="!visibleItems.length" :key="`empty-${facet}`" class="nmg__empty">
          <PmEmptyState
            :icon="emptyState.icon"
            :title="emptyState.title"
            :subtitle="emptyState.subtitle"
            size="sm"
          />
        </div>

        <div v-else key="items" class="nmg__groups">
          <section v-for="group in groupedItems" :key="group.key" class="nmg__group">
            <h3 class="nmg__group-heading">{{ group.label }}</h3>
            <ul class="nmg__grid">
              <li
                v-for="note in group.notes"
                :key="note.id"
                class="nmg__card"
              >
              <v-menu location="bottom end" :offset="6">
                <template #activator="{ props: menuProps }">
                  <v-btn
                    v-bind="menuProps"
                    class="nmg__menu-btn"
                    icon="mdi-dots-vertical"
                    size="small"
                    density="comfortable"
                    variant="text"
                    :ripple="false"
                    :disabled="busy"
                    :aria-label="`${note.title?.trim() || 'Eintrag'}: Aktionen`"
                    @click.stop
                  />
                </template>

                <v-list class="nmg__menu-list" density="compact" min-width="210">
                  <template v-if="facet === 'notes'">
                    <v-list-item prepend-icon="mdi-pencil-outline" title="Umbenennen" @click="startRename(note)" />
                    <v-list-item prepend-icon="mdi-content-copy" title="Als Vorlage speichern" @click="saveNoteAsTemplate(note)" />
                    <v-divider class="nmg__menu-divider" />
                    <v-list-item
                      class="nmg__menu-item--danger"
                      prepend-icon="mdi-trash-can-outline"
                      title="In Papierkorb"
                      @click="trashNote(note)"
                    />
                  </template>
                  <template v-else>
                    <v-list-item prepend-icon="mdi-note-plus-outline" title="Neue Notiz erstellen" @click="createNoteFromTemplate(note)" />
                    <v-list-item prepend-icon="mdi-pencil-outline" title="Umbenennen" @click="startRename(note)" />
                    <v-divider class="nmg__menu-divider" />
                    <v-list-item
                      class="nmg__menu-item--danger"
                      prepend-icon="mdi-trash-can-outline"
                      title="Vorlage löschen…"
                      @click="requestTemplateDeletion(note)"
                    />
                  </template>
                </v-list>
              </v-menu>

              <div
                class="nmg__card-body"
                :class="{ 'is-clickable': facet === 'notes' }"
                @click="onCardClick(note)"
              >
                <div class="nmg__card-head">
                  <input
                    v-if="editingId === note.id"
                    ref="titleInputRef"
                    v-model="editingTitle"
                    class="nmg__title-input"
                    type="text"
                    maxlength="500"
                    placeholder="Titel …"
                    @click.stop
                    @keydown.enter.prevent="commitRename(note)"
                    @keydown.esc.prevent="cancelRename"
                    @blur="commitRename(note)"
                  />
                  <span
                    v-else
                    class="nmg__title"
                    :class="{ 'is-untitled': !note.title?.trim() }"
                  >
                    {{ note.title?.trim() || 'Ohne Titel' }}
                  </span>
                </div>

                <p class="nmg__snippet">{{ snippet(note) }}</p>

                <div v-if="facet === 'notes'" class="nmg__card-tags" @click.stop>
                  <NoteTagBar
                    :tag-ids="(note.tags || []).map((t) => t.id)"
                    :all-tags="allTagsForCard(note)"
                    compact
                    :create-tag-by-name="tagStore.ensureTagIdByName"
                    :load-tags="tagStore.fetchTags"
                    @update:tag-ids="(ids) => applyCardTags(note, ids)"
                  />
                </div>

                <div class="nmg__card-foot">
                  <span class="nmg__date">{{ formatDate(note.updated_at) }}</span>
                  <span class="nmg__badges">
                    <span
                      v-if="facet === 'notes' && note.link_count > 0"
                      class="nmg__badge nmg__badge--links"
                      :title="`${note.link_count} Verknüpfung${note.link_count === 1 ? '' : 'en'}`"
                    >
                      <v-icon size="12">mdi-link-variant</v-icon>
                      {{ note.link_count }}
                    </span>
                  </span>
                </div>
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
          <div class="nmg__tag-sidebar-title">
            <span>Tags</span>
          </div>
          <div class="nmg__tag-sidebar-actions">
            <button
              type="button"
              class="nmg__tag-sidebar-action nmg__tag-sidebar-close"
              aria-label="Tag-Filter schließen"
              @click="tagSidebarOpen = false"
            >
              <v-icon size="16">mdi-close</v-icon>
            </button>
          </div>
        </div>

        <div class="nmg__tag-cloud" role="group" aria-label="Verwendete Tags">
          <button
            type="button"
            class="nmg__tag-cloud-all"
            :class="{ 'is-active': !activeTagId }"
            :aria-pressed="String(!activeTagId)"
            @click="activeTagId = null"
          >
            <span>Alle Notizen</span>
            <span class="nmg__tag-cloud-count">{{ allNotes.length }}</span>
          </button>

          <div v-if="tagCloudItems.length" class="nmg__tag-cloud-items">
            <button
              v-for="tag in tagCloudItems"
              :key="tag.id"
              type="button"
              class="nmg__tag-cloud-chip"
              :class="[`is-size-${tag.size}`, { 'is-active': activeTagId === tag.id }]"
              :aria-pressed="String(activeTagId === tag.id)"
              @click="toggleTagFilter(tag.id)"
            >
              <span class="nmg__tag-cloud-name">{{ tag.name }}</span>
              <span class="nmg__tag-cloud-count">{{ tag.count }}</span>
            </button>
          </div>
          <div v-else class="nmg__tag-cloud-empty">
            <v-icon size="20">mdi-tag</v-icon>
            <span>Noch keine verwendeten Tags</span>
            <small>Weise einer Notiz ein Tag zu. Danach erscheint es hier als Filter.</small>
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

const props = defineProps({
  facet: { type: String, default: 'notes' },
  searchQuery: { type: String, default: '' },
  searchScope: { type: String, default: 'all' },
});

const emit = defineEmits(['open-note', 'changed']);

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

// Die Häufigkeit beeinflusst nur dezent die Typografie der Wolke. Bei gleich
// häufig genutzten Tags bleibt alles auf derselben mittleren Stufe.
const tagCloudItems = computed(() => {
  const tags = usedTags.value;
  if (!tags.length) return [];
  const counts = tags.map((tag) => tag.count);
  const min = Math.min(...counts);
  const max = Math.max(...counts);
  return tags.map((tag) => {
    const ratio = max === min ? 0.5 : (tag.count - min) / (max - min);
    const size = ratio >= 0.68 ? 'lg' : ratio <= 0.32 ? 'sm' : 'md';
    return { ...tag, size };
  });
});

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
    emit('open-note', note.id);
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
  width: clamp(232px, 18vw, 280px);
  min-height: 0;
  flex: none;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 17px 16px 22px;
  border-left: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 78%, transparent);
  background: color-mix(in srgb, var(--pm-app-surface, #fff) 38%, transparent);
}

.nmg__tag-sidebar-head,
.nmg__tag-sidebar-title,
.nmg__tag-sidebar-actions {
  display: flex;
  align-items: center;
}

.nmg__tag-sidebar-head {
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}

.nmg__tag-sidebar-title {
  color: var(--pm-text, #0f172a);
  font-size: 0.82rem;
  font-weight: 680;
  letter-spacing: 0.01em;
}

.nmg__tag-sidebar-actions {
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
  width: 28px;
  height: 28px;
  border-radius: 8px;
}

.nmg__tag-sidebar-action:hover,
.nmg__tag-sidebar-action:focus-visible,
.nmg__tag-sidebar-toggle:hover,
.nmg__tag-sidebar-toggle:focus-visible {
  background: var(--pm-accent-wash, rgba(0, 107, 117, 0.12));
  color: var(--pm-accent-strong, #00555f);
  outline: none;
}

.nmg__tag-sidebar-close,
.nmg__tag-sidebar-toggle {
  display: none;
}

.nmg__tag-cloud {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nmg__tag-cloud-all,
.nmg__tag-cloud-chip {
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 82%, transparent);
  background: color-mix(in srgb, var(--pm-app-surface-raised, #fff) 46%, transparent);
  color: var(--pm-muted, #64748b);
  cursor: pointer;
  transition: color 120ms ease, border-color 120ms ease, background 120ms ease;
}

.nmg__tag-cloud-all {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  padding: 7px 10px;
  border-radius: 10px;
  font-size: 0.76rem;
  font-weight: 590;
  text-align: left;
}

.nmg__tag-cloud-items {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  align-items: center;
  gap: 7px;
}

.nmg__tag-cloud-empty {
  display: grid;
  justify-items: start;
  gap: 6px;
  padding: 14px 10px;
  color: var(--pm-muted, #64748b);
}

.nmg__tag-cloud-empty .v-icon {
  color: var(--pm-accent, #006b75);
  opacity: 0.44;
}

.nmg__tag-cloud-empty > span {
  font-size: 0.76rem;
  font-weight: 610;
}

.nmg__tag-cloud-empty > small {
  max-width: 23ch;
  font-size: 0.7rem;
  line-height: 1.5;
  opacity: 0.78;
}

.nmg__tag-cloud-chip {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  padding: 4px 9px;
  border-radius: 999px;
  font-weight: 540;
  line-height: 1.35;
}

.nmg__tag-cloud-chip.is-size-sm {
  font-size: 0.72rem;
}

.nmg__tag-cloud-chip.is-size-md {
  font-size: 0.79rem;
}

.nmg__tag-cloud-chip.is-size-lg {
  font-size: 0.86rem;
  font-weight: 610;
}

.nmg__tag-cloud-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nmg__tag-cloud-count {
  flex: none;
  font-variant-numeric: tabular-nums;
  opacity: 0.62;
  font-size: 0.7rem;
}

.nmg__tag-cloud-all:hover,
.nmg__tag-cloud-all:focus-visible,
.nmg__tag-cloud-chip:hover,
.nmg__tag-cloud-chip:focus-visible {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 38%, transparent);
  color: var(--pm-text, #0f172a);
  outline: none;
}

.nmg__tag-cloud-all.is-active,
.nmg__tag-cloud-chip.is-active {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 48%, transparent);
  background: var(--pm-accent-wash, rgba(0, 107, 117, 0.12));
  color: var(--pm-accent-strong, #00555f);
}

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
  padding: 12px 16px 10px;
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

.nmg__groups {
  padding: 2px 16px 22px;
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
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.nmg__card {
  position: relative;
  display: flex;
  height: auto;
  flex-direction: column;
  border: 1px solid var(--pm-document-row-border, rgba(15, 23, 42, 0.06));
  border-radius: 14px;
  background: var(--pm-document-row-bg, var(--pm-app-surface-raised, #fff));
  box-shadow: var(--pm-document-row-shadow, 0 2px 8px rgba(15, 23, 42, 0.08));
  transition: border-color var(--pm-duration-fast, 140ms) ease, background var(--pm-duration-fast, 140ms) ease, box-shadow var(--pm-duration-fast, 140ms) ease, transform var(--pm-duration-fast, 140ms) ease;
}

.nmg__card:hover {
  border-color: var(--pm-document-row-hover-border, color-mix(in srgb, var(--pm-accent) 22%, transparent));
  background: var(--pm-row-hover, rgba(0, 107, 117, 0.03));
  box-shadow: 0 8px 22px -10px rgba(15, 23, 42, 0.28);
  transform: translateY(-1px);
}

.nmg__menu-btn {
  position: absolute;
  top: 7px;
  right: 7px;
  z-index: 3;
  color: var(--pm-muted);
  opacity: 0.5;
  transition: opacity 120ms ease, background 120ms ease, color 120ms ease;
}

.nmg__menu-btn:hover,
.nmg__menu-btn:focus-visible,
.nmg__menu-btn[aria-expanded='true'] {
  background: var(--pm-row-hover, rgba(0, 107, 117, 0.06));
  color: var(--pm-accent, #006b75);
  opacity: 1;
}

.nmg__menu-list {
  padding: 5px;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 76%, transparent);
  border-radius: 12px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.14);
}

.nmg__menu-divider {
  margin: 4px 7px;
}

.nmg__menu-item--danger {
  color: var(--pm-danger, #d95757);
}

.nmg__card-body {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 7px;
  padding: 14px 16px 12px;
}

.nmg__card-body.is-clickable {
  cursor: pointer;
}

.nmg__card-head {
  padding-right: 26px;
}

.nmg__title {
  display: -webkit-box;
  overflow: hidden;
  color: var(--pm-text);
  font-size: 0.95rem;
  font-weight: 650;
  line-height: 1.3;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.nmg__title.is-untitled {
  color: var(--pm-muted);
  font-style: italic;
  font-weight: 560;
}

.nmg__title-input {
  width: 100%;
  padding: 1px 4px;
  border: 1px solid color-mix(in srgb, var(--pm-accent) 45%, transparent);
  border-radius: 6px;
  background: var(--pm-app-surface, #fff);
  color: var(--pm-text);
  font: inherit;
  font-size: 0.95rem;
  font-weight: 650;
  outline: none;
}

.nmg__snippet {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--pm-muted);
  font-size: 0.82rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.nmg__card-tags {
  min-width: 0;
  margin: 3px -16px 0;
  overflow: visible;
  padding: 9px 16px 1px;
  border-top: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 72%, transparent);
}

.nmg__card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
  padding-top: 2px;
}

.nmg__date {
  color: var(--pm-muted);
  font-size: 0.72rem;
  white-space: nowrap;
}

.nmg__badges {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.nmg__badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  border-radius: 100px;
  font-size: 0.7rem;
  font-weight: 600;
  line-height: 1.4;
}

.nmg__badge--links {
  background: color-mix(in srgb, var(--pm-accent) 12%, transparent);
  color: var(--pm-accent, #006b75);
}

@media (max-width: 760px) {
  .nmg__tag-sidebar {
    position: absolute;
    z-index: 8;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(280px, calc(100% - 34px));
    border-left-color: color-mix(in srgb, var(--pm-divider, #d8dfe1) 92%, transparent);
    background: var(--pm-app-surface, #fff);
    box-shadow: -14px 0 34px rgba(15, 23, 42, 0.12);
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
  .nmg__card,
  .nmg__menu-btn,
  .nmg__tag-sidebar,
  .nmg__tag-sidebar-action,
  .nmg__tag-sidebar-toggle,
  .nmg__tag-cloud-all,
  .nmg__tag-cloud-chip {
    transition-duration: 0ms;
  }
}

:global(.pm-no-animations) .nmg__card,
:global(.pm-no-animations) .nmg__menu-btn,
:global(.pm-no-animations) .nmg__tag-sidebar,
:global(.pm-no-animations) .nmg__tag-sidebar-action,
:global(.pm-no-animations) .nmg__tag-sidebar-toggle,
:global(.pm-no-animations) .nmg__tag-cloud-all,
:global(.pm-no-animations) .nmg__tag-cloud-chip {
  transition-duration: 0ms;
}
</style>
