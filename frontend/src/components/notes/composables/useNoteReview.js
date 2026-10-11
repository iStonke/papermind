import { computed, onBeforeUnmount, reactive, watch } from 'vue';
import { posToDOMRect } from '@tiptap/vue-3';
import { createNoteAIRequest } from './noteAIRequest.js';
import { streamNoteReview } from '../../../api/notes.js';
import {
  NOTE_REVIEW_INPUT_LIMIT,
  parseReviewOutput,
  resolveReviewAnchors,
  summarizeReviewChanges,
} from '../../../utils/noteReview.js';
import {
  applyReviewEdits,
  buildReviewEdit,
  flattenReviewDoc,
  planReviewEdits,
  resolveReviewPositions,
  refreshInlineReviewChange,
  reviewChangesStillValid,
  reviewStructureContext,
} from './noteReviewDoc.js';
import { LIVE_REVIEW_DELAY, LIVE_REVIEW_INTERVAL, liveFormatPreservesText, liveReviewScope } from './noteLiveReview.js';
import { clearReviewDecorations, setReviewDecorations } from '../extensions/reviewDecorations.js';

/*
 * Vorschläge werden einzeln und mit eigenem Undo-Schritt übernommen.
 * Manuelle Änderungen bleiben möglich; Vorschläge zu veränderten Blöcken
 * werden verworfen und übrige Positionen mitgeführt.
 */
const VIEW_STORAGE_KEY = 'pm-note-review-preferences-v1';
const SORT_MODES = ['order', 'type'];
const FILTER_MODES = ['open', 'rejected', 'all'];

export function useNoteReview({
  editor,
  props,
  overlays,
  onCheckpoint,
  stream = streamNoteReview,
  getStorage = () => window.localStorage,
  now = () => Date.now(),
}) {
  const requests = createNoteAIRequest();
  const reviewAvailable = computed(() => props.reviewAvailable ?? props.aiAvailable);
  let savedView = {};
  try { savedView = JSON.parse(getStorage().getItem(VIEW_STORAGE_KEY)) || {}; } catch { /* Speicherung ist optional. */ }

  const review = reactive({
    open: false,
    loading: false,
    paused: false,
    pending: false,
    mode: 'live',
    preview: '',
    changes: [],
    // Entscheidung je Verbesserung: 'open' (unentschieden) | 'rejected'.
    // Angenommene werden sofort in die Notiz geschrieben und aus der Liste
    // entfernt – sie tauchen daher hier nicht auf.
    status: {},
    focusId: null,
    hoverId: null,
    showMarks: true,
    instructionOpen: false,
    instruction: '',
    error: '',
    notice: '',
    provider: '',
    model: '',
    fallbackFrom: '',
    baseText: '',
    empty: false,
    stale: false,
    sort: SORT_MODES.includes(savedView.sort) ? savedView.sort : 'order',
    filter: FILTER_MODES.includes(savedView.filter) ? savedView.filter : 'open',
  });
  watch(() => [review.sort, review.filter], ([sort, filter]) => {
    try { getStorage().setItem(VIEW_STORAGE_KEY, JSON.stringify({ sort, filter })); } catch { /* Ansicht bleibt ohne Storage nutzbar. */ }
  }, { flush: 'sync' });

  let liveTimer = null;
  let checkedThrough = new WeakMap();
  let nextChangeId = 1;
  let nextLiveReviewAt = 0;

  function cancelScheduledReview() {
    clearTimeout(liveTimer);
    liveTimer = null;
    review.pending = false;
  }
  function scheduleReview() {
    cancelScheduledReview();
    if (!review.open || review.paused || review.loading || !reviewAvailable.value) return;
    review.pending = true;
    liveTimer = setTimeout(() => {
      liveTimer = null;
      review.pending = false;
      if (editor.value?.view?.composing) { scheduleReview(); return; }
      void requestReview();
    }, Math.max(LIVE_REVIEW_DELAY, nextLiveReviewAt - now()));
  }

  let applyingReviewEdit = false;
  let reviewEditMappings = [];
  let reviewRetried = false; // erlaubt genau einen stillen Neuversuch pro Anfrage
  // Zwischengespeicherte Verbesserungen, damit ein Aus-/Einblenden des Panels sie
  // nicht verwirft, solange der Notiztext unverändert ist.
  let reviewCache = null; // Vorschläge und Ansicht beim Ausblenden

  // Fokus wird nur per Klick gesetzt – Hover löst bewusst KEINE Fokus-Behandlung
  // mehr aus (das Überfahren der Liste wirkte sonst zu unruhig).
  const effectiveFocusId = computed(() => review.focusId);
  const focusChange = computed(() => review.changes.find((c) => c.id === effectiveFocusId.value) || null);
  const changeStatus = (id) => review.status[id] || 'open';
  const openCount = computed(() => review.changes.filter((c) => changeStatus(c.id) === 'open').length);
  const rejectedCount = computed(() => review.changes.filter((c) => changeStatus(c.id) === 'rejected').length);

  // Nach Sortierung (Reihenfolge/Typ) aufbereitet; Filter/Abschnitte darüber.
  const REVIEW_TYPE_RANK = { fix: 0, format: 1, add: 2 };
  function sortReviewList(list) {
    if (review.sort === 'type') {
      return [...list].sort((a, b) => (REVIEW_TYPE_RANK[a.cat] - REVIEW_TYPE_RANK[b.cat]) || (a.from - b.from));
    }
    return [...list].sort((a, b) => a.from - b.from);
  }
  const openCards = computed(() => sortReviewList(review.changes.filter((c) => changeStatus(c.id) === 'open')));
  const rejectedCards = computed(() => sortReviewList(review.changes.filter((c) => changeStatus(c.id) === 'rejected')));
  // Flache, gefilterte Liste (für Tests/Fokuslogik).
  const reviewCards = computed(() => {
    if (review.filter === 'open') return openCards.value;
    if (review.filter === 'rejected') return rejectedCards.value;
    return sortReviewList(review.changes);
  });
  // Abschnitte „Offen"/„Abgelehnt"; der Filter wählt, welche gezeigt werden.
  const reviewSections = computed(() => {
    const sections = [];
    if (review.filter === 'all' || review.filter === 'open') sections.push({ key: 'open', label: 'Offen', cards: openCards.value });
    if (review.filter === 'all' || review.filter === 'rejected') sections.push({ key: 'rejected', label: 'Abgelehnt', cards: rejectedCards.value });
    return sections;
  });
  const reviewSummary = computed(() => summarizeReviewChanges(review.changes));

  function syncDecorations() {
    const ed = editor.value;
    if (!ed || ed.isDestroyed) return;
    if (!review.open || !review.showMarks || !review.changes.length) {
      clearReviewDecorations(ed);
      return;
    }
    const focus = effectiveFocusId.value;
    // Jede offene/abgelehnte Anker-Stelle trägt Unterstreichung + Ziffer;
    // abgelehnte werden gedämpft, der Fokus legt einen Softton darüber.
    const specs = review.changes
      .filter((c) => c.found)
      .map((c) => {
        const rejected = changeStatus(c.id) === 'rejected';
        const underline = ['pm-review-underline', `pm-review-underline--${c.cat}`];
        const number = ['pm-review-num', `pm-review-num--${c.cat}`];
        if (c.id === focus) { underline.push('is-focus'); number.push('is-focus'); }
        if (rejected) { underline.push('is-rejected'); number.push('is-rejected'); }
        return {
          id: c.id,
          focused: c.id === focus,
          from: c.from,
          to: c.to,
          class: underline.join(' '),
          number: c.number,
          numberClass: number.join(' '),
        };
      });
    setReviewDecorations(ed, specs);
  }

  function resetReviewState() {
    cancelScheduledReview();
    requests.cancel();
    checkedThrough = new WeakMap();
    nextChangeId = 1;
    review.paused = false;
    review.mode = 'live';
    review.open = false;
    review.loading = false;
    review.preview = '';
    review.changes = [];
    review.status = {};
    review.focusId = null;
    review.hoverId = null;
    review.instructionOpen = false;
    review.instruction = '';
    review.error = '';
    review.notice = '';
    review.provider = '';
    review.model = '';
    review.fallbackFrom = '';
    review.baseText = '';
    review.empty = false;
    review.stale = false;
  }

  // Momentaufnahme der aktuellen Vorschläge + Entscheidungen für später sichern –
  // aber nur, wenn der Notiztext seit dem Auflösen unverändert ist.
  function snapshotReviewCache() {
    const ed = editor.value;
    if (!ed || ed.isDestroyed || !review.open) return false;
    if (flattenReviewDoc(ed.state.doc).text !== review.baseText) return false;
    reviewCache = {
      baseText: review.baseText,
      doc: ed.state.doc,
      changes: review.changes.map((c) => ({ ...c })),
      status: { ...review.status },
      instruction: review.instruction,
      provider: review.provider,
      model: review.model,
      fallbackFrom: review.fallbackFrom,
      stale: review.stale,
      notice: review.notice,
      checkedThrough,
      nextChangeId,
    };
    return true;
  }

  // `keep`: beim Ausblenden die Vorschläge im Cache behalten (statt zu verwerfen).
  function closeReview({ keep = true } = {}) {
    const ed = editor.value;
    if (keep) {
      if (review.open && !snapshotReviewCache()) reviewCache = null;
    } else {
      reviewCache = null;
    }
    resetReviewState();
    if (ed && !ed.isDestroyed) {
      clearReviewDecorations(ed);
    }
  }

  // Track edits synchronously, before a late streamed answer can be applied.
  function onEditorTransaction({ transaction }) {
    if (!transaction.docChanged) return;
    // Undo can restore a previously checked node object. Invalidate every
    // changed block even when its identity is already in the cache.
    const start = transaction.before.content.findDiffStart(transaction.doc.content);
    if (start != null) {
      const end = transaction.before.content.findDiffEnd(transaction.doc.content)?.b ?? start;
      transaction.doc.forEach((node, pos) => {
        if (pos <= end && pos + node.nodeSize > start) checkedThrough.delete(node);
      });
    }
    if (applyingReviewEdit) { reviewEditMappings.push(transaction.mapping); return; }
    reviewCache = null;
    if (!review.open) return;
    // Finish one local generation before scheduling another. Its snapshot
    // guard discards outdated output when the user writes in the meantime.
    review.preview = '';
    review.error = '';
    review.stale = true;
    review.focusId = null;
    review.hoverId = null;
    const mapped = review.changes.map(change => ({
      ...change,
      from: transaction.mapping.map(change.from, 1),
      to: transaction.mapping.map(change.to, -1),
      blockFrom: transaction.mapping.map(change.blockFrom, 1),
      blockTo: transaction.mapping.map(change.blockTo, -1),
    })).filter(change => change.from < change.to && change.blockFrom <= change.blockTo)
      .map(change => reviewChangesStillValid(transaction.doc, [change]) ? change
      : refreshInlineReviewChange(transaction.doc, change))
      .filter(change => change && change.from < change.to);
    review.changes = mapped;
    review.status = Object.fromEntries(mapped.map(change => [change.id, changeStatus(change.id)]));
    review.empty = mapped.length === 0;
    const flattened = flattenReviewDoc(transaction.doc);
    review.baseText = flattened.text;
    syncDecorations();
    scheduleReview();
  }
  watch(editor, (ed, _previous, onCleanup) => {
    ed?.on?.('transaction', onEditorTransaction);
    // Auch ein Klick auf die bereits gesetzte Schreibmarke hebt den Kartenfokus
    // auf. Programmatisches Fokussieren beim Annehmen bleibt davon unberührt.
    const dom = ed?.view?.dom;
    const onPointerDown = (event) => {
      if (event.button === 0 && review.open) clearFocus();
    };
    dom?.addEventListener?.('pointerdown', onPointerDown);
    onCleanup(() => {
      ed?.off?.('transaction', onEditorTransaction);
      dom?.removeEventListener?.('pointerdown', onPointerDown);
    });
  }, { immediate: true, flush: 'sync' });

  async function startReview({ mode = 'live' } = {}) {
    const ed = editor.value;
    if (!ed || !reviewAvailable.value || review.loading || review.open) return;

    const { text } = flattenReviewDoc(ed.state.doc);
    overlays.open('review');

    // Unverändert seit dem Ausblenden? Dann die gemerkten Vorschläge samt
    // Entscheidungen ohne erneute KI-Anfrage wiederherstellen.
    const restorable = reviewCache && reviewCache.doc.eq(ed.state.doc);
    const cachedChanges = restorable ? reviewCache.changes : null;
    const cachedStatus = restorable ? reviewCache.status : null;

    resetReviewState();
    review.open = true;
    review.baseText = text;

    if (restorable) {
      Object.assign(review, {
        instruction: reviewCache.instruction,
        provider: reviewCache.provider,
        model: reviewCache.model,
        fallbackFrom: reviewCache.fallbackFrom,
        stale: reviewCache.stale,
        notice: reviewCache.notice,
      });
      checkedThrough = reviewCache.checkedThrough;
      nextChangeId = reviewCache.nextChangeId;
      review.changes = cachedChanges;
      review.status = cachedStatus;
      review.empty = !cachedChanges.length;
      syncDecorations();
      if (review.stale || liveReviewScope(ed.state.doc, checkedThrough)) scheduleReview();
      return;
    }
    reviewCache = null;

    if (!text.trim()) {
      review.empty = true;
      review.error = '';
      return;
    }
    await requestReview({ mode });
  }

  async function requestReview({ retry = false, mode = 'live', scope: retryScope = null } = {}) {
    const ed = editor.value;
    if (!ed || ed.isDestroyed || !review.open || review.loading || !reviewAvailable.value) return;
    cancelScheduledReview();
    if (!retry) reviewRetried = false;
    const doc = ed.state.doc;
    const current = flattenReviewDoc(doc);
    const scope = retryScope || (mode === 'live' ? liveReviewScope(doc, checkedThrough) : {
      ...current, structure: reviewStructureContext(doc), from: 0, to: doc.content.size,
      checked: Array.from({ length: doc.childCount }, (_, i) => [doc.child(i), flattenReviewDoc(doc.child(i)).text.length]),
    });
    if (!scope || !scope.text.trim()) {
      review.stale = false;
      review.empty = review.changes.length === 0;
      return;
    }
    if (scope.text.length > NOTE_REVIEW_INPUT_LIMIT) {
      review.error = 'Die Notiz ist für eine Gesamtprüfung zu lang. Die laufende Prüfung arbeitet abschnittsweise.';
      return;
    }
    review.baseText = current.text;
    review.preview = '';
    review.error = '';
    review.notice = '';
    review.mode = mode;
    review.loading = true;
    nextLiveReviewAt = now() + LIVE_REVIEW_INTERVAL;

    const request = requests.begin();
    const noteId = props.noteId;
    let needsRetry = false;
    let completed = false;
    try {
      await stream({
        note_text: scope.text,
        note_structure: scope.structure,
        extra_instruction: mode === 'full' ? review.instruction.trim() : '',
        mode,
        retry,
      }, {
        signal: request.signal,
        onEvent: (event) => {
          if (!request.isCurrent() || props.noteId !== noteId || editor.value?.state.doc !== doc) return;
          if (event.type === 'meta') {
            review.provider = event.provider || '';
            review.model = event.model || '';
            review.fallbackFrom = event.fallback_from || '';
          } else if (event.type === 'delta') {
            review.preview += event.text || '';
          }
        },
      });
      if (!request.isCurrent() || props.noteId !== noteId || editor.value?.state.doc !== doc) return;
      const parsed = finishReview(scope, mode);
      if (!parsed.ok && mode === 'full' && !reviewRetried) needsRetry = true;
      else if (!parsed.ok) review.error = parsed.error || 'Die Antwort ließ sich nicht sicher auswerten. Bitte erneut versuchen.';
      else {
        completed = true;
        for (const [node, through] of scope.checked) checkedThrough.set(node, through);
        review.stale = Boolean(liveReviewScope(doc, checkedThrough));
      }
    } catch (error) {
      if (request.isCurrent() && editor.value?.state.doc === doc && error?.name !== 'AbortError' && review.open) {
        if (error?.code === 'review_incomplete' && mode === 'full' && !reviewRetried) needsRetry = true;
        else review.error = error?.message || 'Überarbeitung fehlgeschlagen.';
      }
    } finally {
      if (request.isCurrent()) {
        review.loading = false;
        if (needsRetry) {
          reviewRetried = true;
          void requestReview({ retry: true, mode, scope });
        } else if (editor.value?.state.doc !== doc || (completed && review.stale)) scheduleReview();
      }
    }
  }

  function finishReview(scope, mode) {
    const ed = editor.value;
    if (!ed) return { ok: false, error: '' };
    const parsed = parseReviewOutput(review.preview);
    if (!parsed.ok) return parsed;
    const raw = mode === 'live' ? parsed.changes.filter(c => c.cat !== 'add' && c.anchor !== c.revised).slice(0, 3) : parsed.changes;
    const located = resolveReviewAnchors(scope.text, raw);
    const positioned = resolveReviewPositions(ed.state.doc, scope.map, located)
      .filter(c => c.found && buildReviewEdit(c) && c.from >= scope.from && c.to <= scope.to
        && (mode !== 'live' || (liveFormatPreservesText(c)
          && (c.blockIds?.length || (c.from > c.blockFrom && c.to < c.blockTo)))));
    const skipped = raw.length - positioned.length;
    if (mode === 'live' && skipped) {
      review.notice = skipped === 1
        ? 'Ein unsicherer KI-Hinweis wurde ausgelassen. Du kannst weiterschreiben.'
        : 'Unsichere KI-Hinweise wurden ausgelassen. Du kannst weiterschreiben.';
      if (!positioned.length) return { ok: true, error: '' };
    }
    if (raw.length && !positioned.length) {
      return { ok: false, error: 'Die Verbesserungen ließen sich der Notiz nicht sicher zuordnen.' };
    }
    const previous = review.changes;
    const samePlace = (a, b) => a.cat === b.cat && a.anchor === b.anchor && a.from === b.from && a.to === b.to;
    const merged = previous.filter(c => changeStatus(c.id) === 'rejected' || c.to <= scope.from || c.from >= scope.to);
    for (const change of positioned) {
      const old = previous.find(c => samePlace(c, change) && (changeStatus(c.id) === 'rejected' || c.revised === change.revised));
      if (old && changeStatus(old.id) === 'rejected') continue;
      if (old) merged.push({ ...change, id: old.id, number: old.number });
      else {
        const id = nextChangeId++;
        merged.push({ ...change, id, number: id });
      }
    }
    review.changes = merged.sort((a, b) => a.from - b.from);
    review.status = Object.fromEntries(merged.map(c => [c.id, changeStatus(c.id)]));
    review.empty = !merged.length;
    if (!merged.some(c => c.id === review.focusId)) clearFocus();
    syncDecorations();
    return { ok: true, error: '' };
  }

  // Follow the actual accepted transaction, rather than searching the anchors
  // again: identical words elsewhere must not receive another card's decision.
  function rematerializeRemaining(remaining, statusById) {
    const ed = editor.value;
    if (!ed) return;
    let mapped = remaining;
    for (const mapping of reviewEditMappings) mapped = mapped.map(change => ({
      ...change,
      from: mapping.map(change.from, 1), to: mapping.map(change.to, -1),
      blockFrom: mapping.map(change.blockFrom, 1), blockTo: mapping.map(change.blockTo, -1),
    }));
    reviewEditMappings = [];
    review.baseText = flattenReviewDoc(ed.state.doc).text;
    review.changes = mapped.filter(change => change.from < change.to && change.blockFrom <= change.blockTo)
      .map(change => reviewChangesStillValid(ed.state.doc, [change]) ? change
      : refreshInlineReviewChange(ed.state.doc, change)).filter(change => change && change.from < change.to);
    review.status = Object.fromEntries(review.changes.map(change => [change.id, statusById[change.id] || 'open']));
    review.empty = !review.changes.length;
    if (!review.changes.some(change => change.id === review.focusId)) clearFocus();
    syncDecorations();
  }

  // Annehmen: die einzelne Verbesserung SOFORT in die Notiz schreiben (eigener
  // Undo-Schritt) und aus der Liste entfernen; der Rest wird neu aufgelöst.
  function acceptChange(id) {
    const ed = editor.value;
    if (!ed || ed.isDestroyed) return;
    const change = review.changes.find((c) => c.id === id);
    if (!change || !change.found) return;
    requests.cancel();
    review.loading = false;
    review.preview = '';
    const others = review.changes.filter((c) => c.id !== id);
    const statusById = { ...review.status };
    delete statusById[id];

    if (!reviewChangesStillValid(ed.state.doc, [change])) {
      review.error = 'Der betroffene Abschnitt wurde verändert. Bitte erneut prüfen.';
      return;
    }
    {
      const { edits } = planReviewEdits([change]);
      if (!edits.length) {
        review.error = 'Dieser Vorschlag lässt sich nicht sicher übernehmen. Bitte erneut prüfen.';
        return;
      }
      if (edits.length) {
        clearReviewDecorations(ed);
        reviewEditMappings = [];
        applyingReviewEdit = true;
        try { applyReviewEdits(ed, edits); } finally { applyingReviewEdit = false; }
        onCheckpoint('ai');
      }
    }
    reviewCache = null; // der Text hat sich geändert
    rematerializeRemaining(others, statusById);
    review.stale = true;
    scheduleReview();
  }

  function rejectChange(id) {
    review.status = { ...review.status, [id]: 'rejected' };
    syncDecorations();
  }
  function reopenChange(id) {
    review.status = { ...review.status, [id]: 'open' };
    syncDecorations();
  }
  function setFilter(value) {
    if (FILTER_MODES.includes(value)) review.filter = value;
  }
  function clearFocus() {
    review.focusId = null;
    review.hoverId = null;
  }
  function setFocus(id) {
    review.focusId = review.focusId === id ? null : id;
  }

  // Bringt die Ankerstelle einer Änderung mittig in die Sichtfläche des Editors.
  function scrollToChange(change) {
    const ed = editor.value;
    if (!ed || ed.isDestroyed || !change?.found) return;
    const scroller = ed.view?.dom?.closest?.('.note-workspace-editor__scroll');
    if (!scroller) return;
    let rect;
    try {
      rect = posToDOMRect(ed.view, change.from, change.to);
    } catch {
      return;
    }
    if (!rect) return;
    const base = scroller.getBoundingClientRect();
    const target = scroller.scrollTop + (rect.top - base.top) - base.height / 2 + rect.height / 2;
    scroller.scrollTo({ top: Math.max(0, target), behavior: 'smooth' });
  }

  // Klick auf eine Vorschlagskarte: fokussieren UND zur Stelle im Editor springen.
  function revealChange(id) {
    const willFocus = review.focusId !== id;
    setFocus(id);
    if (willFocus) scrollToChange(review.changes.find((c) => c.id === id));
  }
  function setHover(id) {
    review.hoverId = id;
  }
  function toggleMarks() {
    review.showMarks = !review.showMarks;
  }
  function setSort(value) {
    if (SORT_MODES.includes(value)) review.sort = value;
  }
  function regenerateReview() {
    requests.cancel();
    review.loading = false;
    checkedThrough = new WeakMap();
    return requestReview();
  }
  function reviewWholeNote() {
    requests.cancel();
    review.loading = false;
    review.instructionOpen = false;
    return requestReview({ mode: 'full' });
  }
  function togglePause() {
    review.paused = !review.paused;
    if (review.paused) {
      cancelScheduledReview();
      if (review.mode === 'live') { requests.cancel(); review.loading = false; review.preview = ''; }
    } else scheduleReview();
  }

  // Explizites Verwerfen beendet den Modus. Angenommene Verbesserungen sind
  // bereits in der Notiz; offene/abgelehnte werden verworfen.
  function discardReview() {
    closeReview({ keep: false });
  }

  function toggleReview() {
    // Ausblenden über den Kopf-Button bewahrt die Vorschläge (Cache); nur der
    // „Verwerfen"-Button im Panel verwirft sie endgültig.
    if (review.open) closeReview({ keep: true });
    else startReview();
  }

  // Dekorationen folgen Auswahl, Fokus und Sichtbarkeit.
  watch(
    () => [review.open, review.showMarks, effectiveFocusId.value, JSON.stringify(review.status)],
    syncDecorations,
  );

  overlays.register('review', closeReview);
  onBeforeUnmount(discardReview);
  watch(() => props.noteId, discardReview, { flush: 'sync' });
  watch(reviewAvailable, available => {
    if (!available) { cancelScheduledReview(); requests.cancel(); review.loading = false; }
    else if (review.open) scheduleReview();
  }, { flush: 'sync' });

  return {
    editor,
    review,
    effectiveFocusId,
    focusChange,
    reviewCards,
    reviewSections,
    reviewSummary,
    openCount,
    rejectedCount,
    startReview,
    toggleReview,
    requestReview,
    regenerateReview,
    reviewWholeNote,
    togglePause,
    acceptChange,
    rejectChange,
    reopenChange,
    setFilter,
    setFocus,
    clearFocus,
    revealChange,
    setHover,
    toggleMarks,
    setSort,
    discardReview,
    closeReview,
  };
}
