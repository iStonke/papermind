// Accounts for retained strings and decoded RGBA pixels, rather than counting
// a 200 px thumbnail and a large scan as one equally sized item.
export function imageBytes(value) {
  return String(value?.image || '').length * 2
    + Math.max(0, Number(value?.size?.width) || 0) * Math.max(0, Number(value?.size?.height) || 0) * 4;
}
export function createByteLruCache({ budget = 48 * 1024 * 1024, cost = imageBytes, dispose = () => {} } = {}) {
  const entries = new Map();
  let bytes = 0;
  let protectedKeys = new Set();
  function remove(key) {
    const entry = entries.get(key);
    if (!entry) return;
    entries.delete(key); bytes -= entry.bytes; dispose(entry.value, key);
  }
  function trim() {
    // Protected neighbours get priority, but the byte budget remains a hard bound.
    for (const protect of [false, true]) {
      for (const key of entries.keys()) {
        if (bytes <= budget) return;
        if (protectedKeys.has(key) === protect) remove(key);
      }
    }
  }
  return {
    get size() { return entries.size; }, get bytes() { return bytes; }, budget,
    get(key) {
      const entry = entries.get(key);
      if (!entry) return undefined;
      entries.delete(key); entries.set(key, entry); return entry.value;
    },
    set(key, value) {
      remove(key);
      const size = Math.max(0, cost(value));
      if (size > budget) { dispose(value, key); return false; }
      entries.set(key, { value, bytes: size }); bytes += size; trim(); return entries.has(key);
    },
    protect(keys) { protectedKeys = new Set(keys); trim(); },
    delete: remove, keys: () => entries.keys(),
    clear() { for (const key of [...entries.keys()]) remove(key); },
  };
}
