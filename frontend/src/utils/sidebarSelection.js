const SIDEBAR_SELECTION_STORAGE_KEY = 'pm.sidebar.selection.v1';
export const SIDEBAR_START_AFTER_LOGIN_KEY = 'pm.sidebar.start-after-login';

const VIEW_VALUES = new Set([
  'dashboard',
  'chat',
  'all',
  'notes',
  'imports',
  'untagged',
  'favorites',
  'no_text',
  'trash',
  'tags',
  'categories',
]);
const ROUTE_VALUES = new Set(['dossiers', 'wiki']);
const VALUE_KINDS = new Set(['saved-search', 'tag', 'category']);

function normalizeValue(value) {
  return String(value ?? '').trim().slice(0, 256);
}

export function normalizeSidebarSelection(selection) {
  if (!selection || typeof selection !== 'object') return null;
  const kind = String(selection.kind || '').trim();
  const value = normalizeValue(selection.value);
  if (!value) return null;

  if (kind === 'view' && VIEW_VALUES.has(value)) return { kind, value };
  if (kind === 'route' && ROUTE_VALUES.has(value)) return { kind, value };
  if (VALUE_KINDS.has(kind)) return { kind, value };
  return null;
}

export function readSidebarSelection(storage = globalThis.localStorage) {
  try {
    const raw = storage?.getItem?.(SIDEBAR_SELECTION_STORAGE_KEY);
    return raw ? normalizeSidebarSelection(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

export function persistSidebarSelection(selection, storage = globalThis.localStorage) {
  const normalized = normalizeSidebarSelection(selection);
  if (!normalized) return false;
  try {
    storage?.setItem?.(SIDEBAR_SELECTION_STORAGE_KEY, JSON.stringify(normalized));
    return true;
  } catch {
    return false;
  }
}

export function markSidebarStartAfterLogin(storage = globalThis.sessionStorage) {
  try {
    storage?.setItem?.(SIDEBAR_START_AFTER_LOGIN_KEY, '1');
  } catch {
    // Die Startseite funktioniert weiterhin; nur die einmalige Priorität fehlt.
  }
}

export function consumeSidebarStartAfterLogin(storage = globalThis.sessionStorage) {
  try {
    const shouldUseStart = storage?.getItem?.(SIDEBAR_START_AFTER_LOGIN_KEY) === '1';
    storage?.removeItem?.(SIDEBAR_START_AFTER_LOGIN_KEY);
    return shouldUseStart;
  } catch {
    return false;
  }
}
