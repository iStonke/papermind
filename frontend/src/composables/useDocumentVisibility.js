import { ref } from 'vue';

/**
 * Zentrale Verwaltung der Seiten-Sichtbarkeit (document.hidden).
 *
 * Statt dass jeder Polling-Pfad (OCR-Status, Import-Inbox, ...) einen eigenen
 * `visibilitychange`-Listener registriert, gibt es genau EINEN globalen Listener.
 * Aufrufer abonnieren über `onVisibilityChange(cb)` und lesen bei Bedarf das
 * reaktive `isHidden`. Das bündelt die vorher verstreuten Listener an einer
 * Stelle und vermeidet Duplikate.
 */

const isHidden = ref(typeof document !== 'undefined' ? document.hidden : false);
const listeners = new Set();
let installed = false;

function handleVisibilityChange() {
  isHidden.value = document.hidden;
  for (const callback of listeners) {
    try {
      callback(document.hidden);
    } catch {
      /* ein fehlerhafter Abonnent darf die anderen nicht blockieren */
    }
  }
}

function ensureInstalled() {
  if (installed || typeof document === 'undefined') {
    return;
  }
  document.addEventListener('visibilitychange', handleVisibilityChange);
  installed = true;
}

export function useDocumentVisibility() {
  ensureInstalled();
  return {
    isHidden,
    /**
     * Registriert einen Callback, der bei jedem Sichtbarkeitswechsel mit dem
     * aktuellen `document.hidden` aufgerufen wird. Gibt eine Abmeldefunktion
     * zurück (im onBeforeUnmount aufrufen).
     */
    onVisibilityChange(callback) {
      if (typeof callback !== 'function') {
        return () => {};
      }
      listeners.add(callback);
      return () => listeners.delete(callback);
    }
  };
}
