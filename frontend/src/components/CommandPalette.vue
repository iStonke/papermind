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
            <kbd class="pm-palette__kbd">{{ modKeyLabel }}K</kbd>
          </div>

          <div
            id="pm-palette-list"
            ref="resultsRef"
            class="pm-palette__results"
            role="listbox"
          >
            <template v-if="flatVisible.length">
              <div v-for="grp in groupedResults" :key="grp.group" class="pm-palette__group">
                <div class="pm-palette__section">{{ grp.label }}</div>
                <div
                  v-for="item in grp.items"
                  :id="`pm-palette-opt-${item.index}`"
                  :key="item.cmd.id"
                  class="pm-palette__row"
                  :class="{ 'pm-palette__row--sel': item.index === selectedIndex }"
                  :data-index="item.index"
                  role="option"
                  :aria-selected="item.index === selectedIndex"
                  @click="runCommand(item.cmd)"
                  @mouseenter="selectedIndex = item.index"
                >
                  <v-icon :icon="item.cmd.icon" size="18" class="pm-palette__row-icon" />
                  <span class="pm-palette__row-label" v-html="item.html"></span>
                </div>
              </div>
            </template>
            <p v-else class="pm-palette__placeholder">
              Kein Treffer für „{{ query }}"
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
import { buildCommands, GROUP_LABELS, GROUP_ORDER } from './commandPalette/commands';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const uiStore = useUiStore();
const allCommands = buildCommands({ uiStore });

const dialogRef = ref(null);
const inputRef = ref(null);
const resultsRef = ref(null);
const query = ref('');
const selectedIndex = ref(0);

const placeholder = 'Aktion oder Suche… (>, #, @)';

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

// Subsequenz-Match auf dem Label (Treffer-Buchstaben hervorgehoben). Fällt es
// durch, greift ein einfacher Keyword-Treffer ohne Hervorhebung.
function matchCommand(cmd, term) {
  const label = cmd.label;
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
  if (cmd.keywords?.some((k) => k.toLowerCase().includes(term))) {
    return { ok: true, html: escapeHtml(label) };
  }
  return { ok: false };
}

const results = computed(() => {
  const term = query.value.trim().toLowerCase();
  const matched = [];
  for (const cmd of allCommands) {
    if (!term) {
      matched.push({ cmd, html: escapeHtml(cmd.label) });
      continue;
    }
    const m = matchCommand(cmd, term);
    if (m.ok) matched.push({ cmd, html: m.html });
  }
  return matched;
});

// Nach Gruppen (in GROUP_ORDER) sortiert; jedem Eintrag wird ein flacher Index
// in visueller Reihenfolge zugewiesen, an dem selectedIndex hängt.
const groupedResults = computed(() => {
  let i = 0;
  const groups = [];
  for (const group of GROUP_ORDER) {
    const items = results.value
      .filter((r) => r.cmd.group === group)
      .map((r) => ({ ...r, index: i++ }));
    if (items.length) groups.push({ group, label: GROUP_LABELS[group], items });
  }
  return groups;
});

const flatVisible = computed(() => groupedResults.value.flatMap((g) => g.items));

const activeDescendantId = computed(() => (
  flatVisible.value.length ? `pm-palette-opt-${selectedIndex.value}` : undefined
));

watch(query, () => { selectedIndex.value = 0; });

function close() {
  emit('update:modelValue', false);
}

function runCommand(cmd) {
  if (!cmd) return;
  close();
  cmd.run();
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
    runCommand(list[selectedIndex.value]?.cmd);
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
