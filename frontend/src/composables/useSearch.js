import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue';

const SEARCH_DEBOUNCE_MS = 300;
const SEARCHABLE_STATUSES = new Set(['imported', 'processing', 'ready', 'failed']);
const SEARCH_SCOPES = new Set(['all', 'title', 'ocr_text', 'document_type', 'correspondent', 'tags']);

function isValidIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

/**
 * Parst den rohen Suchtext und extrahiert Freitext, Status-Filter und Datums-Filter.
 * Unterstützte Operatoren: `status:<wert>` und `date:<von>..<bis>` (ISO-Daten).
 */
function parseSearchText(rawSearch) {
  const normalized = (rawSearch || '').trim();
  if (!normalized) {
    return { q: '', status: '', dateFrom: '', dateTo: '', warning: '' };
  }

  const freeTerms = [];
  const warnings = [];
  let statusFilter = '';
  let dateFrom = '';
  let dateTo = '';

  for (const rawToken of normalized.split(/\s+/)) {
    const token = rawToken.trim();
    const lowerToken = token.toLowerCase();

    if (lowerToken.startsWith('status:')) {
      const statusValue = lowerToken.slice('status:'.length);
      if (SEARCHABLE_STATUSES.has(statusValue)) {
        statusFilter = statusValue;
      } else {
        warnings.push('Ungültiger status: Filter. Er wird als Freitext behandelt.');
        freeTerms.push(token);
      }
      continue;
    }

    if (lowerToken.startsWith('date:')) {
      const rangeValue = token.slice('date:'.length);
      const [fromDate, toDate, extraPart] = rangeValue.split('..');
      const isValidRange =
        !extraPart &&
        isValidIsoDate(fromDate || '') &&
        isValidIsoDate(toDate || '') &&
        fromDate <= toDate;

      if (isValidRange) {
        dateFrom = fromDate;
        dateTo = toDate;
      } else {
        warnings.push('Ungültiger date: Bereich. Er wird als Freitext behandelt.');
        freeTerms.push(token);
      }
      continue;
    }

    freeTerms.push(token);
  }

  return {
    q: freeTerms.join(' ').trim(),
    status: statusFilter,
    dateFrom,
    dateTo,
    warning: warnings[0] || ''
  };
}

/** Liefert den Status-Filterwert für eine gegebene View-ID (Erweiterungspunkt). */
function statusFromView(_viewKey) {
  return null;
}

/**
 * Kapselt den gesamten Suchzustand der App:
 *   - Suchtext und AppBar-Ref
 *   - Geparste Suche (Freitext, Status, Datum)
 *   - Kontextsensitiver Placeholder
 *   - Debounced Dokumenten-Reload
 *   - Synchronisation der Suche in die documentListQuery
 *
 * @param {Object} options
 * @param {import('vue').Reactive} options.documentListQuery       – Reaktives Query-Objekt
 * @param {import('vue').ComputedRef} options.documentListQueryReloadKey – Triggert den debounced Fetch
 * @param {import('vue').Ref}      options.activeView             – Aktive View-ID
 * @param {import('vue').Ref}      options.activeSavedSearchId    – ID des aktiven gespeicherten Ordners
 * @param {import('vue').ComputedRef} options.activeSavedSearchName – Name des aktiven gespeicherten Ordners
 * @param {import('vue').ComputedRef} options.activeTagId         – Aktiv gefilterter Tag
 * @param {import('vue').Ref}      options.tags                   – Alle Tags aus dem Store
 * @param {import('vue').ComputedRef} options.isTagView           – Ob die Tag-Verwaltungsansicht aktiv ist
 * @param {import('vue').Ref}      options.selectedDocumentId     – Ausgewählte Doc-ID
 * @param {Function}               options.patchDocumentListQuery – Mutation der documentListQuery
 * @param {Function}               options.fetchDocuments         – Lädt Dokumente neu
 * @param {Function}               options.resolveToolbarStatus   – Persistierter Status aus der aktuellen Toolbar
 */
export function useSearch({
  documentListQuery,
  documentListQueryReloadKey,
  activeView,
  activeSavedSearchId,
  activeSavedSearchName,
  activeTagId,
  tags,
  isTagView,
  selectedDocumentId,
  patchDocumentListQuery,
  fetchDocuments,
  resolveToolbarStatus = statusFromView
}) {
  const searchText = ref('');
  const searchScope = ref('all');
  const appBarSearchRef = ref(null);
  let searchDebounceTimer = null;

  // ── Computed ────────────────────────────────────────────────────────────────

  const parsedSearch = computed(() => parseSearchText(searchText.value));

  const searchHintMessages = computed(() =>
    parsedSearch.value.warning ? [parsedSearch.value.warning] : []
  );

  const showSnippets = computed(() => Boolean(parsedSearch.value.q));

  const searchPlaceholder = computed(() => {
    if (activeView.value === 'tags') return 'Tags suchen…';
    return 'Suchen…';
  });

  // ── Funktionen ──────────────────────────────────────────────────────────────

  function syncSearchStateToQuery(options = {}) {
    const parsed = parsedSearch.value;
    const resolvedStatus =
      parsed.status || resolveToolbarStatus(activeView.value);
    const normalizedScope = SEARCH_SCOPES.has(searchScope.value) ? searchScope.value : 'all';
    return patchDocumentListQuery(
      {
        q: parsed.q || null,
        searchScope: normalizedScope,
        status: resolvedStatus,
        dateFrom: parsed.dateFrom || null,
        dateTo: parsed.dateTo || null
      },
      options
    );
  }

  function focusSearchFieldInput() {
    const inputEl = appBarSearchRef.value?.$el?.querySelector('input');
    inputEl?.focus?.();
  }

  function triggerSearchNow() {
    syncSearchStateToQuery();
    if (searchDebounceTimer) {
      window.clearTimeout(searchDebounceTimer);
      searchDebounceTimer = null;
    }
    void fetchDocuments(selectedDocumentId.value);
  }

  function onAppBarSearchInput(value) {
    searchText.value = value ?? '';
  }

  function clearSearchFromInput() {
    searchText.value = '';
    triggerSearchNow();
    nextTick(() => {
      focusSearchFieldInput();
    });
  }

  function handleSearchEscape() {
    if (!searchText.value) {
      return;
    }
    clearSearchFromInput();
  }

  // ── Watches ─────────────────────────────────────────────────────────────────

  // Geparste Suche → Query synchronisieren wenn sich Suchwerte oder View ändern
  watch(
    () => [
      parsedSearch.value.q,
      parsedSearch.value.status,
      parsedSearch.value.dateFrom,
      parsedSearch.value.dateTo,
      searchScope.value,
      activeView.value
    ],
    () => {
      if (isTagView.value) {
        return;
      }
      syncSearchStateToQuery();
    }
  );

  // Query-Key-Änderung → debounced Dokumenten-Reload
  watch(documentListQueryReloadKey, () => {
    if (searchDebounceTimer) {
      window.clearTimeout(searchDebounceTimer);
    }
    searchDebounceTimer = window.setTimeout(() => {
      if (isTagView.value) {
        return;
      }
      void fetchDocuments(selectedDocumentId.value);
    }, SEARCH_DEBOUNCE_MS);
  });

  onBeforeUnmount(() => {
    if (searchDebounceTimer) {
      window.clearTimeout(searchDebounceTimer);
    }
  });

  // ── Public API ──────────────────────────────────────────────────────────────

  return {
    searchText,
    searchScope,
    appBarSearchRef,
    parsedSearch,
    searchHintMessages,
    showSnippets,
    searchPlaceholder,
    syncSearchStateToQuery,
    triggerSearchNow,
    focusSearchFieldInput,
    onAppBarSearchInput,
    clearSearchFromInput,
    handleSearchEscape
  };
}
