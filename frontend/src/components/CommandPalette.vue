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
              aria-label="Aktion oder Suche"
            />
            <kbd class="pm-palette__kbd">{{ modKeyLabel }}K</kbd>
          </div>

          <div class="pm-palette__results">
            <p class="pm-palette__placeholder">
              Suche, Aktionen und Sprungziele folgen in den nächsten Schritten.
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

const props = defineProps({
  modelValue: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const dialogRef = ref(null);
const inputRef = ref(null);
const query = ref('');

const placeholder = 'Aktion oder Suche… (>, #, @)';

const modKeyLabel = computed(() => {
  const platform = typeof navigator !== 'undefined'
    ? (navigator.platform || navigator.userAgent || '')
    : '';
  return /Mac|iPhone|iPad|iPod/i.test(platform) ? '⌘' : 'Ctrl+';
});

function close() {
  emit('update:modelValue', false);
}

function onKeydown(event) {
  if (matchesShortcut(event, SHORTCUT_ACTIONS.CANCEL)) {
    event.preventDefault();
    event.stopPropagation();
    close();
    return;
  }
  // Fokus-Falle: im Gerüst ist das Eingabefeld das einzige fokussierbare
  // Element – Tab hält den Fokus dort (erweitern, sobald Ergebnisse per
  // aria-activedescendant navigierbar sind).
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
  padding: 8px 6px;
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
