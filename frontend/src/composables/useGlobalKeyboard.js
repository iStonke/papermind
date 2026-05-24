import { onMounted, onBeforeUnmount } from 'vue';

/**
 * Registriert einen globalen keydown-Handler auf window.
 * Lifecycle-Hooks (add/remove EventListener) werden intern verwaltet.
 *
 * @param {(event: KeyboardEvent) => void} handler
 */
export function useGlobalKeyboard(handler) {
  onMounted(() => {
    window.addEventListener('keydown', handler);
  });

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', handler);
  });
}
