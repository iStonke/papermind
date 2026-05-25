import { useShortcutScope } from '../keyboard/shortcuts';

/**
 * Registriert einen globalen keydown-Handler auf window.
 * Lifecycle-Hooks (add/remove EventListener) werden intern verwaltet.
 *
 * @param {(event: KeyboardEvent) => void} handler
 */
export function useGlobalKeyboard(handler) {
  return useShortcutScope(handler);
}
