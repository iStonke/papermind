import { computed, ref } from 'vue';

/**
 * Kleine asynchrone Command-History für reversible UI-Aktionen.
 *
 * Commands werden erst nach einer erfolgreich ausgeführten Aktion eingetragen.
 * Schlägt Undo/Redo fehl, bleibt der Eintrag auf seinem bisherigen Stapel.
 */
export function useCommandHistory({ limit = 50 } = {}) {
  const undoStack = ref([]);
  const redoStack = ref([]);
  const busy = ref(false);

  const canUndo = computed(() => !busy.value && undoStack.value.length > 0);
  const canRedo = computed(() => !busy.value && redoStack.value.length > 0);
  const undoLabel = computed(() => undoStack.value.at(-1)?.label || '');
  const redoLabel = computed(() => redoStack.value.at(-1)?.label || '');

  function record(command) {
    if (!command || typeof command.undo !== 'function' || typeof command.redo !== 'function') {
      throw new TypeError('Ein History-Command benötigt undo und redo.');
    }
    undoStack.value = [...undoStack.value, command].slice(-Math.max(1, limit));
    redoStack.value = [];
  }

  function clear() {
    undoStack.value = [];
    redoStack.value = [];
  }

  async function undo() {
    if (!canUndo.value) return null;
    const command = undoStack.value.at(-1);
    busy.value = true;
    try {
      await command.undo();
      undoStack.value = undoStack.value.slice(0, -1);
      redoStack.value = [...redoStack.value, command];
      return command;
    } finally {
      busy.value = false;
    }
  }

  async function redo() {
    if (!canRedo.value) return null;
    const command = redoStack.value.at(-1);
    busy.value = true;
    try {
      await command.redo();
      redoStack.value = redoStack.value.slice(0, -1);
      undoStack.value = [...undoStack.value, command].slice(-Math.max(1, limit));
      return command;
    } finally {
      busy.value = false;
    }
  }

  return {
    busy,
    canUndo,
    canRedo,
    undoLabel,
    redoLabel,
    record,
    clear,
    undo,
    redo,
  };
}
