<template>
  <Teleport to="#pm-overlays">
    <Transition name="pm-palette">
      <div
        v-if="modelValue"
        class="pm-palette-scrim"
        role="presentation"
        @mousedown.self="close"
      >
        <div
          ref="dialogRef"
          class="pm-palette"
          role="dialog"
          aria-modal="true"
          aria-label="Befehle und Suche"
          @keydown="onKeydown"
        >
          <div class="pm-palette__search">
            <span class="pm-palette__search-icon" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2" stroke-linecap="round"
                   stroke-linejoin="round">
                <circle cx="11" cy="11" r="7" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </span>
            <span v-if="contextTitle" class="pm-palette__scope" :title="contextTitle">
              <v-icon icon="mdi-file-document-outline" size="14" aria-hidden="true" />
              <span class="pm-palette__scope-text">{{ contextTitle }}</span>
            </span>
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              class="pm-palette__input"
              :placeholder="placeholder"
              autocomplete="off"
              spellcheck="false"
              role="combobox"
              aria-controls="pm-palette-list"
              aria-expanded="true"
              aria-autocomplete="list"
              :aria-activedescendant="activeDescendantId"
              aria-label="Aktion oder Suche"
            />
            <kbd v-if="modeLabel" class="pm-palette__kbd pm-palette__kbd--mode">{{ modeLabel }}</kbd>
            <kbd class="pm-palette__kbd">{{ modKeyLabel }}K</kbd>
          </div>

          <div
            id="pm-palette-list"
            ref="resultsRef"
            class="pm-palette__results"
            role="listbox"
          >
            <template v-if="flatVisible.length">
              <div v-for="grp in groupedResults" :key="grp.key" class="pm-palette__group">
                <div v-if="grp.label" class="pm-palette__section">{{ grp.label }}</div>
                <div
                  v-for="item in grp.items"
                  :id="`pm-palette-opt-${item.index}`"
                  :key="item.entry.id"
                  class="pm-palette__row"
                  :class="{ 'pm-palette__row--sel': item.index === selectedIndex, 'pm-stagger-item': justOpened }"
                  :style="{ '--pm-i': item.index }"
                  :data-index="item.index"
                  role="option"
                  :aria-selected="item.index === selectedIndex"
                  @click="runEntry(item.entry)"
                  @mouseenter="selectIndex(item.index)"
                >
                  <v-icon :icon="item.entry.icon" size="18" class="pm-palette__row-icon" />
                  <span class="pm-palette__row-label" v-html="item.html"></span>
                </div>
              </div>
            </template>
            <p v-else class="pm-palette__placeholder">
              Kein Treffer für „{{ parsed.term }}"
            </p>
          </div>

          <div class="pm-palette__footer">
            <span><kbd class="pm-palette__kbd">↑↓</kbd> navigieren</span>
            <span><kbd class="pm-palette__kbd">↵</kbd> öffnen</span>
            <span><kbd class="pm-palette__kbd">esc</kbd> schließen</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue';
import { matchesShortcut, SHORTCUT_ACTIONS } from '../keyboard/shortcuts';
import { useUiStore } from '../stores/ui';
import { useDocumentStore } from '../stores/documents';
import { useTagStore } from '../stores/tags';
import { useCategoryStore } from '../stores/categories';
import { useCorrespondentStore } from '../stores/correspondents';
import { buildCommands } from './commandPalette/commands';
import { escapeHtml, parsePrefix, buildGroups, reconcileSelection } from './commandPalette/matching';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const uiStore = useUiStore();
const documentStore = useDocumentStore();
const tagStore = useTagStore();
const categoryStore = useCategoryStore();
const correspondentStore = useCorrespondentStore();

const baseCommands = buildCommands({ uiStore });

const dialogRef = ref(null);
const inputRef = ref(null);
const resultsRef = ref(null);
const query = ref('');
const selectedIndex = ref(0);
const selectedEntryId = ref(null);
// Steuert die Einblende-Kaskade: nur beim Öffnen, nicht bei jeder Filterung.
const justOpened = ref(false);
let staggerTimer = null;

const placeholder = 'Suchen oder Aktion… (>, #, @)';
const DOCUMENT_LIMIT = 6;

// Präfix-Modi grenzen die Ergebnisse auf eine Gruppe ein.
const MODE_GROUP = { '>': 'action', '#': 'tag', '@': 'correspondent' };
const MODE_LABEL = { '>': 'Aktionen', '#': 'Tags', '@': 'Korrespondenten' };

// Renderreihenfolge + Sektions-Überschriften. Leeres Label = ohne Überschrift.
const GROUP_CONFIG = [
  { key: 'context', label: 'Für dieses Dokument' },
  { key: 'action', label: 'Aktionen' },
  { key: 'nav', label: 'Springe zu' },
  { key: 'document', label: 'Dokumente', limit: DOCUMENT_LIMIT },
  { key: 'tag', label: 'Tags' },
  { key: 'correspondent', label: 'Korrespondenten' },
  { key: 'type', label: 'Dokumenttypen' },
];

const modKeyLabel = computed(() => {
  const platform = typeof navigator !== 'undefined'
    ? (navigator.platform || navigator.userAgent || '')
    : '';
  return /Mac|iPhone|iPad|iPod/i.test(platform) ? '⌘' : 'Ctrl+';
});

function documentTitle(doc) {
  return String(doc?.display_name || '').trim()
    || String(doc?.original_filename || '').trim()
    || 'Unbenanntes Dokument';
}

// Präfix (>, #, @) vom Suchbegriff trennen.
const parsed = computed(() => parsePrefix(query.value, MODE_GROUP));

const modeLabel = computed(() => (parsed.value.mode ? MODE_LABEL[parsed.value.mode] : ''));

// Kontextbewusstsein: ist im Reader ein Dokument offen, erscheinen oben
// Aktionen „Für dieses Dokument" (auch bei leerem Feld; beim Tippen mitgeranked).
const contextTitle = computed(() => {
  const doc = documentStore.selectedDocumentDetail;
  return doc ? documentTitle(doc) : '';
});

function contextEntries() {
  const doc = documentStore.selectedDocumentDetail;
  if (!doc) return [];
  return [
    {
      id: 'ctx-details',
      group: 'context',
      icon: 'mdi-information-outline',
      label: 'Details & Metadaten öffnen',
      keywords: ['details', 'metadaten', 'info', 'aufbewahrung', 'tags', 'korrespondent'],
      run: () => uiStore.requestWorkspace('contextDetails'),
    },
    {
      id: 'ctx-download',
      group: 'context',
      icon: 'mdi-download-outline',
      label: 'Herunterladen',
      keywords: ['download', 'herunterladen', 'speichern', 'pdf'],
      run: () => uiStore.requestWorkspace('contextDownload'),
    },
    {
      id: 'ctx-trash',
      group: 'context',
      icon: 'mdi-trash-can-outline',
      label: 'In den Papierkorb',
      keywords: ['papierkorb', 'löschen', 'trash', 'entfernen'],
      run: () => uiStore.requestWorkspace('contextTrash'),
    },
  ];
}

// Dokumente, Tags und Dokumenttypen tauchen erst auf, sobald gesucht wird (oder
// ein passender Präfix-Modus aktiv ist) – sonst bliebe die leere Palette voll.
function dynamicEntries() {
  const entries = [];
  for (const doc of documentStore.documents) {
    entries.push({
      id: `doc-${doc.id}`,
      group: 'document',
      icon: 'mdi-file-document-outline',
      label: documentTitle(doc),
      run: () => uiStore.requestWorkspace('openDocument', doc.id),
    });
  }
  for (const tag of tagStore.tags) {
    entries.push({
      id: `tag-${tag.id}`,
      group: 'tag',
      icon: 'mdi-tag-outline',
      label: tag.name,
      run: () => uiStore.requestWorkspace('tagFilter', tag.id),
    });
  }
  for (const correspondent of correspondentStore.correspondents) {
    entries.push({
      id: `corr-${correspondent.id}`,
      group: 'correspondent',
      icon: 'mdi-card-account-details-outline',
      label: correspondent.name,
      run: () => uiStore.requestWorkspace('correspondentFilter', correspondent.id),
    });
  }
  for (const category of categoryStore.sortedCategories) {
    entries.push({
      id: `type-${category.id}`,
      group: 'type',
      icon: 'mdi-shape-outline',
      label: category.name,
      run: () => uiStore.requestWorkspace('typeFilter', category.name),
    });
  }
  return entries;
}

const view = computed(() => {
  const { mode, term } = parsed.value;
  const showDynamic = term.length > 0 || Boolean(mode);

  let entries = showDynamic
    ? [...contextEntries(), ...baseCommands, ...dynamicEntries()]
    : [...contextEntries(), ...baseCommands];

  // Leeres Feld: nur die häufig genutzten Sprungziele (primary) zeigen – die
  // übrigen bleiben per Tippen auffindbar.
  if (!showDynamic) {
    entries = entries.filter((entry) => entry.group !== 'nav' || entry.primary);
  }

  const groups = buildGroups(entries, {
    term,
    restrictGroup: mode ? MODE_GROUP[mode] : null,
    groupOrder: GROUP_CONFIG,
  });

  // Volltext-Zeile: reicht den Begriff an die echte OCR-Suche des Workspace
  // weiter (Merge der Backend-Treffer in die Palette selbst ist Phase 2).
  if (term && !mode) {
    const label = `„${term}" in allen Dokumenten suchen`;
    const index = groups.reduce((n, g) => n + g.items.length, 0);
    groups.push({
      key: 'fulltext',
      label: '',
      items: [{
        entry: {
          id: 'fulltext',
          group: 'fulltext',
          icon: 'mdi-file-search-outline',
          label,
          run: () => uiStore.requestWorkspace('search', term),
        },
        html: escapeHtml(label),
        index,
      }],
    });
  }

  const flat = groups.flatMap((g) => g.items.map((it) => it.entry));
  return { groups, flat };
});

const groupedResults = computed(() => view.value.groups);
const flatVisible = computed(() => view.value.flat);

const activeDescendantId = computed(() => (
  flatVisible.value.length ? `pm-palette-opt-${selectedIndex.value}` : undefined
));

watch(query, () => {
  selectedIndex.value = 0;
  selectedEntryId.value = null;
  justOpened.value = false; // Tippen stoppt die Einblende-Kaskade
});

// Tags, Korrespondenten und Dokumenttypen können eintreffen, während die
// Palette bereits geöffnet ist. Ihre Einfügung darf eine bestehende Auswahl
// nicht von einem Eintrag auf einen anderen verschieben.
watch(flatVisible, (entries) => {
  const nextIndex = reconcileSelection(entries, selectedEntryId.value, selectedIndex.value);
  selectedIndex.value = nextIndex;
  selectedEntryId.value = entries[nextIndex]?.id || null;
}, { flush: 'sync' });

function selectIndex(index) {
  const entries = flatVisible.value;
  const nextIndex = reconcileSelection(entries, null, index);
  selectedIndex.value = nextIndex;
  selectedEntryId.value = entries[nextIndex]?.id || null;
}

function close() {
  emit('update:modelValue', false);
}

function runEntry(entry) {
  if (!entry) return;
  close();
  entry.run();
}

function consumePaletteKey(event) {
  event.preventDefault();
  // Die Palette liegt als Teleport über der Anwendung. Ihre Navigation darf
  // deshalb nicht zugleich Shortcuts oder Enter-Handler im Hintergrund lösen.
  event.stopPropagation();
}

async function scrollSelectedIntoView() {
  await nextTick();
  resultsRef.value
    ?.querySelector(`.pm-palette__row[data-index="${selectedIndex.value}"]`)
    ?.scrollIntoView({ block: 'nearest' });
}

function onKeydown(event) {
  if (matchesShortcut(event, SHORTCUT_ACTIONS.CANCEL)) {
    consumePaletteKey(event);
    close();
    return;
  }
  const list = flatVisible.value;
  if (event.key === 'ArrowDown') {
    consumePaletteKey(event);
    if (list.length) selectIndex((selectedIndex.value + 1) % list.length);
    scrollSelectedIntoView();
    return;
  }
  if (event.key === 'ArrowUp') {
    consumePaletteKey(event);
    if (list.length) selectIndex((selectedIndex.value - 1 + list.length) % list.length);
    scrollSelectedIntoView();
    return;
  }
  if (event.key === 'Enter') {
    consumePaletteKey(event);
    runEntry(list[selectedIndex.value]);
    return;
  }
  // Fokus-Falle: das Eingabefeld ist das einzige fokussierbare Element; die
  // Ergebnisliste wird per aria-activedescendant navigiert.
  if (event.key === 'Tab') {
    consumePaletteKey(event);
    inputRef.value?.focus();
  }
}

// immediate: true, damit auch das allererste Öffnen den Fokus setzt – beim
// ersten Mount ist modelValue bereits true, ein reiner Change-Watcher würde
// dann nicht feuern. Beim Schließen wandert der Fokus zurück zum vorher
// fokussierten Element (Fokus-Wiederherstellung für Tastatur/Screenreader).
let previouslyFocused = null;
watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      previouslyFocused = typeof document !== 'undefined' ? document.activeElement : null;
      query.value = '';
      selectedIndex.value = 0;
      selectedEntryId.value = null;
      // Ergebnisse beim Öffnen einkaskadieren; nach dem Durchlauf wieder aus,
      // damit spätere Updates (z. B. nachgeladene Tags) nicht erneut kaskadieren.
      justOpened.value = true;
      if (staggerTimer) clearTimeout(staggerTimer);
      staggerTimer = setTimeout(() => { justOpened.value = false; }, 520);
      // Dokumenttypen & Korrespondenten sicher vorhanden, falls die Sidebar sie
      // noch nicht lud.
      categoryStore.ensureLoaded?.();
      correspondentStore.ensureLoaded?.();
      await nextTick();
      inputRef.value?.focus();
    } else {
      justOpened.value = false;
      if (staggerTimer) { clearTimeout(staggerTimer); staggerTimer = null; }
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus();
        previouslyFocused = null;
      }
    }
  },
  { immediate: true },
);
</script>

<style scoped>
.pm-palette-scrim {
  position: fixed;
  inset: 0;
  z-index: 2500;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 12vh 16px 16px;
  /* Die Palette ist ein fokussiertes Modal, keine Drawer-Ansicht: Der
     Drawer-Scrim ist absichtlich transparent und würde den Hintergrund hier
     nahezu unverändert lassen. */
  background: rgba(15, 23, 42, 0.64);
}

.pm-palette {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 560px;
  max-height: 70vh;
  overflow: hidden;
  color: var(--pm-text);
  background: var(--pm-content-surface);
  border: 1px solid var(--pm-divider);
  border-radius: 18px;
  box-shadow: var(--pm-shadow);
}

.pm-palette__search {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 15px;
  border-bottom: 1px solid var(--pm-divider);
}

.pm-palette__search-icon {
  display: flex;
  color: var(--pm-muted);
}

.pm-palette__scope {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 210px;
  padding: 2px 8px;
  font-size: 12px;
  color: var(--pm-chip-text);
  background: var(--pm-chip-bg);
  border-radius: 6px;
  white-space: nowrap;
}

.pm-palette__scope-text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.pm-palette__input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: var(--pm-text);
  caret-color: var(--pm-accent);
}

.pm-palette__input::placeholder {
  color: var(--pm-muted);
}

.pm-palette__kbd {
  padding: 1px 6px;
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--pm-muted);
  border: 1px solid var(--pm-divider);
  border-radius: 5px;
}

.pm-palette__kbd--mode {
  color: var(--pm-accent-text);
  border-color: var(--pm-accent);
}

.pm-palette__results {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px;
}

.pm-palette__section {
  padding: 11px 12px 4px;
  font-size: 11px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--pm-muted);
}

.pm-palette__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background var(--pm-duration-fast, 140ms) var(--pm-easing, ease);
}

.pm-palette__row-icon {
  color: var(--pm-muted);
}

.pm-palette__row-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-size: 14px;
  color: var(--pm-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pm-palette__row-label :deep(mark) {
  background: transparent;
  color: var(--pm-accent);
  font-weight: 500;
}

.pm-palette__row--sel {
  background: var(--pm-selected);
}

.pm-palette__row--sel .pm-palette__row-label,
.pm-palette__row--sel .pm-palette__row-icon,
.pm-palette__row--sel .pm-palette__row-label :deep(mark) {
  color: var(--pm-accent-text);
}

.pm-palette__placeholder {
  margin: 0;
  padding: 26px 12px;
  text-align: center;
  font-size: 14px;
  color: var(--pm-muted);
}

.pm-palette__footer {
  display: flex;
  gap: 16px;
  padding: 9px 14px;
  font-size: 11px;
  color: var(--pm-muted);
  border-top: 1px solid var(--pm-divider);
}

/* Sanfte, zusammenhängende Öffnung ohne Überschwingen: Die Palette hebt sich
   nur minimal aus dem abgedunkelten Hintergrund. */
.pm-palette-enter-active,
.pm-palette-leave-active {
  transition: opacity var(--pm-duration-normal, 210ms) ease-out;
}
.pm-palette-enter-active .pm-palette {
  transition: transform var(--pm-duration-normal, 210ms) cubic-bezier(0.22, 1, 0.36, 1),
    opacity var(--pm-duration-normal, 210ms) ease-out;
}
.pm-palette-leave-active .pm-palette {
  transition: transform var(--pm-duration-fast, 140ms) var(--pm-easing-accel, ease-in),
    opacity var(--pm-duration-fast, 140ms) ease-in;
}
.pm-palette-enter-from,
.pm-palette-leave-to {
  opacity: 0;
}
.pm-palette-leave-to .pm-palette {
  transform: translateY(-6px) scale(0.99);
  opacity: 0;
}
.pm-palette-enter-from .pm-palette {
  transform: translateY(-10px) scale(0.985);
}
</style>
