import { onScopeDispose, shallowRef, toValue, watch } from 'vue';

export function useImportFieldFocus(document) {
  const focused = shallowRef(null);
  const deferred = new Map();
  const key = (id, field) => `${id}:${field}`;
  function release(field) {
    const previous = focused.value;
    if (!previous || field && previous.field !== field) return;
    focused.value = null;
    const token = key(previous.id, previous.field);
    const apply = deferred.get(token);
    deferred.delete(token);
    apply?.();
  }
  function focus(field) {
    field = field === 'name' ? 'title' : field;
    if (!field) return;
    const id = toValue(document)?.id;
    if (!id || focused.value?.id === id && focused.value?.field === field) return;
    release();
    focused.value = { id, field };
  }
  function defer(id, field, apply) {
    if (focused.value?.id !== id || focused.value?.field !== field) return false;
    deferred.set(key(id, field), apply);
    return true;
  }
  function reset() { focused.value = null; deferred.clear(); }
  watch(() => toValue(document)?.id, id => {
    const field = focused.value?.field;
    release();
    // The same input can retain DOM focus while the preview changes documents.
    if (id && field) focused.value = { id, field };
  });
  onScopeDispose(reset);
  return { focus, blur: field => release(field === 'name' ? 'title' : field), defer, reset };
}
