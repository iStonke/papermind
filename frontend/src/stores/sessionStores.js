import { defineStore, getActivePinia } from 'pinia';
import { toRaw, unref } from 'vue';

const stores = new WeakMap();
function clone(value) {
  const raw = toRaw(unref(value));
  if (raw instanceof Map) return new Map([...raw].map(([key, item]) => [key, clone(item)]));
  if (raw instanceof Set) return new Set(raw);
  if (raw instanceof Date) return new Date(raw);
  if (Array.isArray(raw)) return raw.map(clone);
  if (raw && Object.getPrototypeOf(raw) === Object.prototype) {
    return Object.fromEntries(Object.entries(raw).map(([key, item]) => [key, clone(item)]));
  }
  return raw;
}

/** Capture defaults when a store is created, including setup stores. */
export function defineSessionStore(...args) {
  const useStore = defineStore(...args);
  function useSessionStore(...parameters) {
    const store = useStore(...parameters);
    const pinia = parameters[0] || getActivePinia();
    if (!stores.has(pinia)) stores.set(pinia, new Map());
    const registered = stores.get(pinia);
    if (!registered.has(store)) registered.set(store, clone(store.$state));
    return store;
  }
  useSessionStore.$id = useStore.$id;
  return useSessionStore;
}

export function resetSessionStores(pinia = getActivePinia()) {
  for (const [store, defaults] of stores.get(pinia) || []) {
    store.$patch((state) => {
      for (const key of Object.keys(state)) {
        if (!(key in defaults)) delete state[key];
      }
      for (const [key, value] of Object.entries(defaults)) state[key] = clone(value);
    });
    store.resetPrivateState?.();
  }
}
