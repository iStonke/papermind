import { ref, watch } from 'vue';

const STORAGE_KEY = 'pm-notes-list-preferences-v1';
const SORT_MODES = ['updated', 'created', 'title'];
const DATE_RANGES = ['', 'today', 'last_7_days', 'last_30_days'];

export function useNoteListPreferences(defaultSort, getStorage = () => window.localStorage) {
  let saved = {};
  try { saved = JSON.parse(getStorage().getItem(STORAGE_KEY)) || {}; } catch { /* Storage is optional. */ }
  let hasSavedSort = SORT_MODES.includes(saved.sortMode);
  const normalizeSort = value => SORT_MODES.includes(value) ? value : 'updated';
  const sortMode = ref(hasSavedSort ? saved.sortMode : normalizeSort(defaultSort()));
  const dateRange = ref(DATE_RANGES.includes(saved.dateRange) ? saved.dateRange : '');
  const notebookFilter = ref(typeof saved.notebookFilter === 'string' ? saved.notebookFilter : '');

  watch(defaultSort, value => {
    // Asynchronously loaded account defaults must not replace a saved choice.
    if (!hasSavedSort) sortMode.value = normalizeSort(value);
  });
  watch([sortMode, dateRange, notebookFilter], () => {
    hasSavedSort = true;
    try {
      getStorage().setItem(STORAGE_KEY, JSON.stringify({
        sortMode: sortMode.value, dateRange: dateRange.value, notebookFilter: notebookFilter.value,
      }));
    } catch { /* Keep the list usable when storage is unavailable. */ }
  }, { flush: 'sync' });

  return { sortMode, dateRange, notebookFilter };
}
