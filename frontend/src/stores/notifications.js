import { computed, reactive } from 'vue';

const MAX_VISIBLE_NOTIFICATIONS = 2;
const DEDUPE_WINDOW_MS = 1500;

const DEFAULT_TIMEOUTS_BY_TYPE = {
  success: 3000,
  info: 4000,
  warning: 5000,
  error: 6000
};

const state = reactive({
  visible: [],
  queue: []
});

const timerById = new Map();
const recentByKey = new Map();

function createId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `notification-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function pruneRecent(now) {
  for (const [key, ts] of recentByKey.entries()) {
    if (now - ts > DEDUPE_WINDOW_MS) {
      recentByKey.delete(key);
    }
  }
}

function defaultTimeoutForType(type) {
  return DEFAULT_TIMEOUTS_BY_TYPE[type] ?? DEFAULT_TIMEOUTS_BY_TYPE.info;
}

function clearTimer(id) {
  const timerState = timerById.get(id);
  if (!timerState?.timerHandle) {
    return;
  }
  window.clearTimeout(timerState.timerHandle);
  timerState.timerHandle = null;
}

function findVisibleById(id) {
  return state.visible.find((notification) => notification.id === id) || null;
}

function scheduleDismiss(id) {
  const timerState = timerById.get(id);
  const notification = findVisibleById(id);
  if (!timerState || !notification) {
    return;
  }
  clearTimer(id);
  if (timerState.remainingMs <= 0) {
    dismiss(id);
    return;
  }
  timerState.startedAt = Date.now();
  timerState.timerHandle = window.setTimeout(() => dismiss(id), timerState.remainingMs);
}

function activateFromQueue() {
  while (state.visible.length < MAX_VISIBLE_NOTIFICATIONS && state.queue.length > 0) {
    const notification = state.queue.shift();
    if (!notification) {
      break;
    }
    state.visible.push(notification);
    timerById.set(notification.id, {
      remainingMs: notification.timeoutMs,
      startedAt: 0,
      timerHandle: null
    });
    scheduleDismiss(notification.id);
  }
}

function isDuplicate(type, message) {
  const key = `${type}::${message}`.trim();
  const now = Date.now();
  pruneRecent(now);
  const latest = recentByKey.get(key);
  if (latest && now - latest <= DEDUPE_WINDOW_MS) {
    return true;
  }
  recentByKey.set(key, now);
  return false;
}

function notify({ type = 'info', title = '', message = '', timeoutMs } = {}) {
  const normalizedMessage = String(message || '').trim();
  if (!normalizedMessage) {
    return null;
  }

  const normalizedType = ['success', 'info', 'warning', 'error'].includes(type) ? type : 'info';
  if (isDuplicate(normalizedType, normalizedMessage)) {
    return null;
  }

  const notification = {
    id: createId(),
    type: normalizedType,
    title: String(title || '').trim() || null,
    message: normalizedMessage,
    timeoutMs: Number(timeoutMs || defaultTimeoutForType(normalizedType)),
    createdAt: Date.now()
  };

  if (state.visible.length < MAX_VISIBLE_NOTIFICATIONS) {
    state.visible.push(notification);
    timerById.set(notification.id, {
      remainingMs: notification.timeoutMs,
      startedAt: 0,
      timerHandle: null
    });
    scheduleDismiss(notification.id);
  } else {
    state.queue.push(notification);
  }

  return notification.id;
}

function dismiss(id) {
  if (!id) {
    return;
  }
  clearTimer(id);
  timerById.delete(id);

  const visibleIndex = state.visible.findIndex((notification) => notification.id === id);
  if (visibleIndex >= 0) {
    state.visible.splice(visibleIndex, 1);
    activateFromQueue();
    return;
  }

  const queuedIndex = state.queue.findIndex((notification) => notification.id === id);
  if (queuedIndex >= 0) {
    state.queue.splice(queuedIndex, 1);
  }
}

function clearAll() {
  for (const notification of state.visible) {
    clearTimer(notification.id);
  }
  timerById.clear();
  state.visible.splice(0, state.visible.length);
  state.queue.splice(0, state.queue.length);
}

function pause(id) {
  const timerState = timerById.get(id);
  if (!timerState?.timerHandle) {
    return;
  }
  const elapsed = Date.now() - timerState.startedAt;
  timerState.remainingMs = Math.max(0, timerState.remainingMs - elapsed);
  clearTimer(id);
}

function resume(id) {
  const timerState = timerById.get(id);
  if (!timerState) {
    return;
  }
  scheduleDismiss(id);
}

export function mapApiError(error, fallbackMessage = 'Aktion fehlgeschlagen.') {
  const fallback = String(fallbackMessage || 'Aktion fehlgeschlagen.').trim();
  const message = error instanceof Error ? error.message : String(error || '').trim();
  if (!message) {
    return fallback;
  }

  const normalized = message.toLowerCase();
  if (
    normalized.includes('failed to fetch') ||
    normalized.includes('networkerror') ||
    normalized.includes('netzwerk') ||
    normalized.includes('keine verbindung')
  ) {
    return 'Keine Verbindung zum Server.';
  }

  const statusMatch = message.match(/\b(4\d{2}|5\d{2})\b/);
  const statusCode = statusMatch ? Number(statusMatch[1]) : null;
  if (statusCode === 404) {
    return 'Nicht gefunden.';
  }
  if (statusCode === 413) {
    return 'Datei zu groß.';
  }
  if (statusCode === 422) {
    return 'Ungültige Eingabe.';
  }

  if (/^request failed/i.test(message)) {
    return fallback;
  }
  return message;
}

/**
 * Loggt einen Fehler im Dev-Modus auf der Konsole.
 * Kein UI-Feedback — für bewusst stille Fehler gedacht.
 */
export function logDevError(error, context = '') {
  if (import.meta.env.DEV) {
    const prefix = context ? `[PaperMind:${context}]` : '[PaperMind]';
    console.error(prefix, error);
  }
}

/**
 * Zentraler Fehler-Handler: mapApiError + notify + Dev-Log in einem Aufruf.
 *
 * Verwendung:
 *   catch (error) { notifyError(error, 'Dokument konnte nicht geladen werden.'); }
 *
 * @param {unknown} error        - Der gefangene Fehler
 * @param {string}  fallback     - Fallback-Nachricht wenn kein spezifischer Text
 * @param {object}  [options]    - Zusätzliche notify-Optionen (z.B. { title: 'KI' })
 * @returns {string}             - Die angezeigte Fehlermeldung
 */
export function notifyError(error, fallback = 'Aktion fehlgeschlagen.', options = {}) {
  logDevError(error, options.context ?? '');
  const message = mapApiError(error, fallback);
  notify({ type: 'error', message, ...options });
  return message;
}

export function useNotifications() {
  return {
    visibleNotifications: computed(() => state.visible),
    queuedNotifications: computed(() => state.queue),
    notify,
    notifyError,
    logDevError,
    dismissNotification: dismiss,
    clearAllNotifications: clearAll,
    pauseNotificationTimer: pause,
    resumeNotificationTimer: resume
  };
}
