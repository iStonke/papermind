// A token rotation keeps the same generation; logout/account changes do not.
let generation = 0;
let ownerId = '';
const resetListeners = new Set();

export function apiSessionGeneration() { return generation; }
export function apiSessionOwner() { return ownerId; }

export function assertApiSession(expected) {
  if (expected !== generation) {
    const error = new Error('Die Sitzung hat sich geändert.');
    error.name = 'AbortError';
    error.code = 'SESSION_CHANGED';
    throw error;
  }
}

export function onApiSessionReset(listener) {
  resetListeners.add(listener);
  return () => resetListeners.delete(listener);
}

export function resetApiSession(owner = '') {
  generation += 1;
  ownerId = String(owner || '');
  for (const listener of [...resetListeners]) listener();
}
