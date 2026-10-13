import { computed, reactive, ref, watch } from 'vue';

const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);

/** Keep drafts and save acknowledgements attached to an ID, never to the open row. */
export function useRecordAutosave({ items, readDraft, toPayload, validate, persist, delay = 700 }) {
  const selectedId = ref(null);
  const records = reactive(new Map());
  const timers = new Map();
  const jobs = new Map();

  function dirty(record) {
    return !same(toPayload(record.draft), record.base);
  }

  function ensure(item) {
    if (!records.has(item.id)) {
      const draft = readDraft(item);
      records.set(item.id, { draft, base: toPayload(draft), state: 'idle', saving: false });
    }
    return records.get(item.id);
  }

  function clearTimer(id) {
    clearTimeout(timers.get(id));
    timers.delete(id);
  }

  function schedule(id = selectedId.value, immediate = false) {
    const record = records.get(id);
    if (!record) return;
    clearTimer(id);
    if (!record.saving) {
      record.state = dirty(record) ? (validate(record.draft) ? 'pending' : 'invalid') : 'idle';
    }
    if (immediate) return save(id);
    if (dirty(record) && validate(record.draft)) {
      timers.set(id, setTimeout(() => { void save(id); }, delay));
    }
  }

  function field(key, fallback = '') {
    return computed({
      get: () => records.get(selectedId.value)?.draft[key] ?? fallback,
      set: value => {
        const record = records.get(selectedId.value);
        if (!record || record.draft[key] === value) return;
        record.draft[key] = value;
        schedule();
      },
    });
  }

  function save(id = selectedId.value) {
    clearTimer(id);
    if (jobs.has(id)) return jobs.get(id);
    const record = records.get(id);
    if (!record) return Promise.resolve(true);
    // Defer the loop so the job is registered even if no network request is needed.
    const job = Promise.resolve().then(async () => {
      while (dirty(record)) {
        if (!validate(record.draft)) {
          record.state = 'invalid';
          return false;
        }
        const snapshot = toPayload(record.draft);
        record.saving = true;
        record.state = 'saving';
        try {
          const acknowledged = await persist(id, snapshot);
          record.base = acknowledged ? toPayload(readDraft(acknowledged)) : snapshot;
        } catch {
          // Preserve the draft and show a retry; the store reports the API error.
          record.state = 'error';
          return false;
        } finally {
          record.saving = false;
        }
        // New input made while awaiting the response is saved in the next iteration.
      }
      if (record.state !== 'idle') record.state = 'saved';
      return true;
    }).finally(() => jobs.delete(id));
    jobs.set(id, job);
    return job;
  }

  function select(item) {
    if (selectedId.value !== item?.id) void save();
    if (item) ensure(item);
    selectedId.value = item?.id ?? null;
  }

  function forget(id) {
    clearTimer(id);
    records.delete(id);
    if (selectedId.value === id) selectedId.value = null;
  }

  async function flush() {
    return (await Promise.all([...records.keys()].map(id => save(id)))).every(Boolean);
  }

  watch(items, values => {
    for (const item of values) {
      const record = records.get(item.id);
      // A reload or alias change must never replace an active/invalid/failed draft.
      if (!record || record.saving || dirty(record)) continue;
      record.draft = readDraft(item);
      record.base = toPayload(record.draft);
    }
  });

  return {
    selectedId, field, select, save, schedule, forget, flush, cancelScheduled: clearTimer,
    state: computed(() => records.get(selectedId.value)?.state ?? 'idle'),
    stateFor: id => records.get(id)?.state ?? 'idle',
    isDirty: (id = selectedId.value) => {
      const record = records.get(id);
      return record ? dirty(record) : false;
    },
  };
}
