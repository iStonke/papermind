import { onBeforeUnmount, onMounted, watch } from 'vue';

export const SHORTCUT_ACTIONS = Object.freeze({
  ACTIVATE: 'activate',
  CANCEL: 'cancel',
  PRIMARY: 'primary',
  SEARCH_SUBMIT: 'search.submit',
  SEARCH_CANCEL: 'search.cancel',
  STEP_PREVIOUS: 'step.previous',
  STEP_NEXT: 'step.next',
  MOVE_PREVIOUS: 'move.previous',
  MOVE_NEXT: 'move.next',
  HELP: 'help',
  TRASH: 'trash'
});

export const SHORTCUTS = Object.freeze({
  [SHORTCUT_ACTIONS.ACTIVATE]: Object.freeze({ keys: Object.freeze(['Enter', ' ']) }),
  [SHORTCUT_ACTIONS.CANCEL]: Object.freeze({ keys: Object.freeze(['Escape']) }),
  [SHORTCUT_ACTIONS.PRIMARY]: Object.freeze({ keys: Object.freeze(['Enter']) }),
  [SHORTCUT_ACTIONS.SEARCH_SUBMIT]: Object.freeze({ keys: Object.freeze(['Enter']) }),
  [SHORTCUT_ACTIONS.SEARCH_CANCEL]: Object.freeze({ keys: Object.freeze(['Escape']) }),
  [SHORTCUT_ACTIONS.STEP_PREVIOUS]: Object.freeze({ keys: Object.freeze(['ArrowLeft']) }),
  [SHORTCUT_ACTIONS.STEP_NEXT]: Object.freeze({ keys: Object.freeze(['ArrowRight']) }),
  [SHORTCUT_ACTIONS.MOVE_PREVIOUS]: Object.freeze({ keys: Object.freeze(['ArrowLeft', 'ArrowUp']) }),
  [SHORTCUT_ACTIONS.MOVE_NEXT]: Object.freeze({ keys: Object.freeze(['ArrowRight', 'ArrowDown']) }),
  [SHORTCUT_ACTIONS.HELP]: Object.freeze({ keys: Object.freeze(['?']) }),
  [SHORTCUT_ACTIONS.TRASH]: Object.freeze({ keys: Object.freeze(['Backspace']) })
});

function normalizeKey(key) {
  if (key === 'Spacebar') {
    return ' ';
  }
  return key;
}

export function matchesShortcut(event, action) {
  const shortcut = SHORTCUTS[action];
  if (!event || !shortcut) {
    return false;
  }
  return shortcut.keys.includes(normalizeKey(event.key));
}

export function isEditableShortcutTarget(target) {
  const tagName = String(target?.tagName || '').toLowerCase();
  return tagName === 'input' || tagName === 'textarea' || tagName === 'select' || Boolean(target?.isContentEditable);
}

export function handleShortcut(event, action, handler, options = {}) {
  if (!matchesShortcut(event, action)) {
    return false;
  }
  if (options.ignoreEditable !== false && isEditableShortcutTarget(event.target)) {
    return false;
  }
  if (options.prevent !== false) {
    event.preventDefault();
  }
  if (options.stop === true) {
    event.stopPropagation();
  }
  handler?.(event);
  return true;
}

export function useShortcutScope(handler, options = {}) {
  const shouldListen = options.enabled;
  let attached = false;

  function isEnabled() {
    if (typeof shouldListen === 'function') {
      return Boolean(shouldListen());
    }
    if (shouldListen && typeof shouldListen === 'object' && 'value' in shouldListen) {
      return Boolean(shouldListen.value);
    }
    return shouldListen !== false;
  }

  function attach() {
    if (attached || typeof window === 'undefined') {
      return;
    }
    window.addEventListener('keydown', handler);
    attached = true;
  }

  function detach() {
    if (!attached || typeof window === 'undefined') {
      return;
    }
    window.removeEventListener('keydown', handler);
    attached = false;
  }

  function sync() {
    if (isEnabled()) {
      attach();
      return;
    }
    detach();
  }

  onMounted(sync);
  onBeforeUnmount(detach);

  if (shouldListen && typeof shouldListen === 'object' && 'value' in shouldListen) {
    watch(shouldListen, sync);
  }

  return { sync, detach };
}
