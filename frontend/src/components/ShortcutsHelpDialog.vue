<template>
  <BaseDialog
    :model-value="modelValue"
    max-width="480"
    title="Tastaturkürzel"
    header-subtitle="Verfügbare Shortcuts in PaperMind."
    variant="info"
    primary-text="Fertig"
    :show-secondary="false"
    @primary="emit('update:modelValue', false)"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="shortcuts-help">
      <div
        v-for="group in shortcutGroups"
        :key="group.label"
        class="shortcuts-help__group"
      >
        <h3 class="shortcuts-help__group-label">{{ group.label }}</h3>
        <div class="shortcuts-help__rows">
          <div
            v-for="item in group.items"
            :key="item.action"
            class="shortcuts-help__row"
          >
            <span class="shortcuts-help__desc">{{ item.description }}</span>
            <span class="shortcuts-help__keys">
              <kbd
                v-for="key in item.keys"
                :key="key"
                class="shortcuts-help__kbd"
              >{{ formatKey(key) }}</kbd>
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="shortcuts-help shortcuts-help--gestures">
      <div class="shortcuts-help__group">
        <h3 class="shortcuts-help__group-label">Mausgesten</h3>
        <div class="shortcuts-help__rows">
          <div
            v-for="item in mouseGestures"
            :key="item.description"
            class="shortcuts-help__row"
          >
            <span class="shortcuts-help__desc">{{ item.description }}</span>
            <span class="shortcuts-help__keys">
              <kbd class="shortcuts-help__kbd">{{ item.gesture }}</kbd>
            </span>
          </div>
        </div>
      </div>
    </div>
  </BaseDialog>
</template>

<script setup>
import { SHORTCUT_ACTIONS, SHORTCUTS } from '../keyboard/shortcuts';
import BaseDialog from './BaseDialog.vue';

defineProps({
  modelValue: { type: Boolean, default: false }
});

const emit = defineEmits(['update:modelValue']);

const KEY_LABELS = {
  'Enter': '↵ Enter',
  ' ': 'Leertaste',
  'Escape': 'Esc',
  'Backspace': '⌫ Backspace',
  'ArrowLeft': '←',
  'ArrowRight': '→',
  'ArrowUp': '↑',
  'ArrowDown': '↓',
  '?': '?'
};

function formatKey(key) {
  return KEY_LABELS[key] ?? key;
}

function keysFor(action) {
  return SHORTCUTS[action]?.keys ?? [];
}

const shortcutGroups = [
  {
    label: 'Allgemein',
    items: [
      { action: SHORTCUT_ACTIONS.HELP,   description: 'Tastaturkürzel anzeigen', keys: keysFor(SHORTCUT_ACTIONS.HELP) },
      { action: SHORTCUT_ACTIONS.CANCEL, description: 'Dialog / Auswahl schließen', keys: keysFor(SHORTCUT_ACTIONS.CANCEL) }
    ]
  },
  {
    label: 'Suche',
    items: [
      { action: SHORTCUT_ACTIONS.SEARCH_SUBMIT, description: 'Suche bestätigen', keys: keysFor(SHORTCUT_ACTIONS.SEARCH_SUBMIT) },
      { action: SHORTCUT_ACTIONS.SEARCH_CANCEL, description: 'Suche abbrechen',  keys: keysFor(SHORTCUT_ACTIONS.SEARCH_CANCEL) }
    ]
  },
  {
    label: 'Navigation',
    items: [
      { action: SHORTCUT_ACTIONS.MOVE_PREVIOUS, description: 'Vorheriges Element', keys: keysFor(SHORTCUT_ACTIONS.MOVE_PREVIOUS) },
      { action: SHORTCUT_ACTIONS.MOVE_NEXT,     description: 'Nächstes Element',   keys: keysFor(SHORTCUT_ACTIONS.MOVE_NEXT) },
      { action: SHORTCUT_ACTIONS.STEP_PREVIOUS, description: 'Schritt zurück',     keys: keysFor(SHORTCUT_ACTIONS.STEP_PREVIOUS) },
      { action: SHORTCUT_ACTIONS.STEP_NEXT,     description: 'Schritt vor',        keys: keysFor(SHORTCUT_ACTIONS.STEP_NEXT) }
    ]
  },
  {
    label: 'Aktionen',
    items: [
      { action: SHORTCUT_ACTIONS.TRASH,    description: 'Selektiertes Dokument in den Papierkorb', keys: keysFor(SHORTCUT_ACTIONS.TRASH) },
      { action: SHORTCUT_ACTIONS.ACTIVATE, description: 'Element aktivieren / auswählen',           keys: keysFor(SHORTCUT_ACTIONS.ACTIVATE) },
      { action: SHORTCUT_ACTIONS.PRIMARY,  description: 'Primäre Aktion bestätigen',                keys: keysFor(SHORTCUT_ACTIONS.PRIMARY) }
    ]
  }
];

const mouseGestures = [
  { description: 'Auswahlmodus aktivieren & Dokument selektieren', gesture: '⌘ Cmd + Klick' }
];
</script>

<style scoped>
.shortcuts-help {
  display: grid;
  gap: 20px;
}

.shortcuts-help__group-label {
  margin: 0 0 8px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.45);
}

.shortcuts-help__rows {
  display: grid;
  gap: 2px;
}

.shortcuts-help__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px solid var(--pm-divider-soft, rgba(15, 23, 42, 0.06));
}

.shortcuts-help__row:last-child {
  border-bottom: none;
}

.shortcuts-help__desc {
  font-size: 0.88rem;
  color: rgba(var(--v-theme-on-surface), 0.82);
}

.shortcuts-help__keys {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.shortcuts-help__kbd {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  padding: 2px 7px;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 500;
  line-height: 1.4;
  border-radius: 5px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  border: 1px solid rgba(var(--v-theme-on-surface), 0.14);
  color: rgba(var(--v-theme-on-surface), 0.72);
  white-space: nowrap;
}
</style>
