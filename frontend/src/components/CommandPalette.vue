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
                  :class="{ 'pm-palette__row--sel': item.index === selectedIndex }"
                  :data-index="item.index"
                  role="option"
                  :aria-selected="item.index === selectedIndex"
                  @click="runEntry(item.entry)"
                  @mouseenter="selectedIndex = item.index"
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
import { buildCommands } from './commandPalette/commands';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const uiStore = useUiStore();
const documentStore = useDocumentStore();
const tagStore = useTagStore();
const categoryStore = useCategoryStore();

const baseCommands = buildCommands({ uiStore });

const dialogRef = ref(null);
const inputRef = ref(null);
const resultsRef = ref(null);
const query = ref('');
const selectedIndex = ref(0);

const placeholder = 'Suchen oder Aktion… (>, #)';
const DOCUMENT_LIMIT = 6;

// Präfix-Modi grenzen die Ergebnisse auf eine Gruppe ein.
const MODE_GROUP = { '>': 'action', '#': 'tag' };
const MODE_LABEL = { '>': 'Aktionen', '#': 'Tags' };

// Renderreihenfolge + Sektions-Überschriften. Leeres Label = ohne Überschrift.
const GROUP_CONFIG = [
  { key: 'action', label: 'Aktionen' },
  { key: 'nav', label: 'Springe zu' },
  { key: 'document', label: 'Dokumente' },
  { key: 'tag', label: 'Tags' },
  { key: 'type', label: 'Dokumenttypen' },
  { key: 'fulltext', label: '' },
];

const modKeyLabel = computed(() => {
  const platform = typeof navigator !== 'undefined'
    ? (navigator.platform || navigator.userAgent || '')
    : '';
  return /Mac|iPhone|iPad|iPod/i.test(platform) ? '⌘' : 'Ctrl+';
});

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function documentTitle(doc) {
  return String(doc?.display_name || '').trim()
    || String(doc?.original_filename || '').trim()
    || 'Unbenanntes Dokument';
}

// Subsequenz-Match aufs Label (Treffer hervorgehoben); Fallback: Keyword-Treffer.
function matchEntry(entry, term) {
  const label = entry.label;
  const lc = label.toLowerCase();
  let ti = 0;
  let out = '';
  for (let i = 0; i < label.length; i += 1) {
    if (ti < term.length && lc[i] === term[ti]) {
      out += `<mark>${escapeHtml(label[i])}</mark>`;
      ti += 1;
    } else {
      out += escapeHtml(label[i]);
    }
  }
  if (ti === term.length) return { ok: true, html: out };
  if (entry.keywords?.some((k) => k.toLowerCase().includes(term))) {
    return { ok: true, html: escapeHtml(label) };
  }
  return { ok: false };
}

// Präfix (>, #) vom Suchbegriff trennen.
const parsed = computed(() => {
  const raw = query.value;
  const first = raw.charAt(0);
  if (MODE_GROUP[first]) return { mode: first, term: raw.slice(1).trim() };
  return { mode: null, term: raw.trim() };
});

const modeLabel = computed(() => (parsed.value.mode ? MODE_LABEL[parsed.value.mode] : ''));

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
  const lc = term.toLowerCase();
  const showDynamic = term.length > 0 || Boolean(mode);

  const entries = showDynamic ? [...baseCommands, ...dynamicEntries()] : [...baseCommands];

  const byGroup = {};
  for (const entry of entries) {
    if (mode && entry.group !== MODE_GROUP[mode]) continue;
    let html;
    if (!term) {
      html = escapeHtml(entry.label);
    } else {
      const m = matchEntry(entry, lc);
      if (!m.ok) continue;
      html = m.html;
    }
    (byGroup[entry.group] ||= []).push({ entry, html });
  }

  let idx = 0;
  const groups = [];
  for (const cfg of GROUP_CONFIG) {
    if (cfg.key === 'fulltext') continue;
    let items = byGroup[cfg.key];
    if (!items?.length) continue;
    if (cfg.key === 'document') items = items.slice(0, DOCUMENT_LIMIT);
    groups.push({ key: cfg.key, label: cfg.label, items: items.map((it) => ({ ...it, index: idx++ })) });
  }

  // Volltext-Zeile: reicht den Begriff an die echte OCR-Suche des Workspace
  // weiter (Merge der Backend-Treffer in die Palette selbst ist Phase 2).
  if (term && !mode) {
    const label = `„${term}" in allen Dokumenten suchen`;
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
        index: idx++,
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

watch(query, () => { selectedIndex.value = 0; });

function close() {
  emit('update:modelValue', false);
}

function runEntry(entry) {
  if (!entry) return;
  close();
  entry.run();
}

async function scrollSelectedIntoView() {
  await nextTick();
  resultsRef.value
    ?.querySelector(`.pm-palette__row[data-index="${selectedIndex.value}"]`)
    ?.scrollIntoView({ block: 'nearest' });
}

function onKeydown(event) {
  if (matchesShortcut(event, SHORTCUT_ACTIONS.CANCEL)) {
    event.preventDefault();
    event.stopPropagation();
    close();
    return;
  }
  const list = flatVisible.value;
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    if (list.length) selectedIndex.value = (selectedIndex.value + 1) % list.length;
    scrollSelectedIntoView();
    return;
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault();
    if (list.length) selectedIndex.value = (selectedIndex.value - 1 + list.length) % list.length;
    scrollSelectedIntoView();
    return;
  }
  if (event.key === 'Enter') {
    event.preventDefault();
    runEntry(list[selectedIndex.value]);
    return;
  }
  // Fokus-Falle: das Eingabefeld ist das einzige fokussierbare Element; die
  // Ergebnisliste wird per aria-activedescendant navigiert.
  if (event.key === 'Tab') {
    event.preventDefault();
    inputRef.value?.focus();
  }
}

// immediate: true, damit auch das allererste Öffnen den Fokus setzt – beim
// ersten Mount ist modelValue bereits true, ein reiner Change-Watcher würde
// dann nicht feuern.
watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return;
    query.value = '';
    selectedIndex.value = 0;
    // Dokumenttypen sicher vorhanden, falls die Sidebar sie noch nicht lud.
    categoryStore.ensureLoaded?.();
    await nextTick();
    inputRef.value?.focus();
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
  background: var(--pm-drawer-scrim, rgba(15, 23, 42, 0.32));
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

/* Transition über die Kontur-Motion-Tokens; pm-no-animations /
   prefers-reduced-motion setzen die Dauern auf 0ms → automatisch still. */
.pm-palette-enter-active,
.pm-palette-leave-active {
  transition: opacity var(--pm-duration-normal, 210ms) var(--pm-easing, ease);
}
.pm-palette-enter-active .pm-palette,
.pm-palette-leave-active .pm-palette {
  transition: transform var(--pm-duration-normal, 210ms) var(--pm-easing, ease),
    opacity var(--pm-duration-normal, 210ms) var(--pm-easing, ease);
}
.pm-palette-enter-from,
.pm-palette-leave-to {
  opacity: 0;
}
.pm-palette-enter-from .pm-palette,
.pm-palette-leave-to .pm-palette {
  transform: translateY(-8px) scale(0.98);
  opacity: 0;
}
</style>
