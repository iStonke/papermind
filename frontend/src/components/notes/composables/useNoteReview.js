import { computed, onBeforeUnmount, reactive, watch } from 'vue';
import { posToDOMRect } from '@tiptap/vue-3';
import { createNoteAIRequest } from './noteAIRequest.js';
import { streamNoteReview } from '../../../api/notes.js';
import {
  NOTE_REVIEW_INPUT_LIMIT,
  parseReviewOutput,
  resolveReviewAnchors,
  reviewDefaultAccepted,
  summarizeReviewChanges,
} from '../../../utils/noteReview.js';
import {
  applyReviewEdits,
  buildReviewEdit,
  flattenReviewDoc,
  planReviewEdits,
  resolveReviewPositions,
  reviewChangesStillValid,
  reviewStructureContext,
} from './noteReviewDoc.js';
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
}) {
  const requests = createNoteAIRequest();
  let savedView = {};
  try { savedView = JSON.parse(getStorage().getItem(VIEW_STORAGE_KEY)) || {}; } catch { /* Speicherung ist optional. */ }

  const review = reactive({
    open: false,
    loading: false,
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

  let baseMap = [];
  let applyingReviewEdit = false;
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
      return [...list].sort((a, b) => (REVIEW_TYPE_RANK[a.cat] - REVIEW_TYPE_RANK[b.cat]) || ((a.number || 0) - (b.number || 0)));
    }
    return [...list].sort((a, b) => (a.number || 0) - (b.number || 0));
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
    requests.cancel();
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
    review.provider = '';
    review.model = '';
    review.fallbackFrom = '';
    review.baseText = '';
    review.empty = false;
    review.stale = false;
    baseMap = [];
  }

  // Momentaufnahme der aktuellen Vorschläge + Entscheidungen für später sichern –
  // aber nur, wenn der Notiztext seit dem Auflösen unverändert ist.
  function snapshotReviewCache() {
    const ed = editor.value;
    if (!ed || ed.isDestroyed || !review.open || !review.changes.length) return false;
    if (flattenReviewDoc(ed.state.doc).text !== review.baseText) return false;
    reviewCache = {
      baseText: review.baseText,
      changes: review.changes.map((c) => ({ ...c })),
      status: { ...review.status },
      instruction: review.instruction,
      provider: review.provider,
      model: review.model,
      fallbackFrom: review.fallbackFrom,
      stale: review.stale,
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
    if (!transaction.docChanged || applyingReviewEdit) return;
    reviewCache = null;
    if (!review.open) return;
    requests.cancel();
    review.loading = false;
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
    })).filter(change => change.from < change.to && reviewChangesStillValid(transaction.doc, [change]));
    review.changes = mapped;
    review.status = Object.fromEntries(mapped.map(change => [change.id, changeStatus(change.id)]));
    review.empty = mapped.length === 0;
    const flattened = flattenReviewDoc(transaction.doc);
    review.baseText = flattened.text;
    baseMap = flattened.map;
    syncDecorations();
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

  async function startReview() {
    const ed = editor.value;
    if (!ed || !props.aiAvailable || review.loading || review.open) return;

    const { text, map } = flattenReviewDoc(ed.state.doc);
    overlays.open('review');

    // Unverändert seit dem Ausblenden? Dann die gemerkten Vorschläge samt
    // Entscheidungen ohne erneute KI-Anfrage wiederherstellen.
    const restorable = reviewCache && reviewCache.baseText === text && reviewCache.changes.length;
    const cachedChanges = restorable ? reviewCache.changes : null;
    const cachedStatus = restorable ? reviewCache.status : null;

    resetReviewState();
    baseMap = map;
    review.open = true;
    review.baseText = text;

    if (restorable) {
      Object.assign(review, {
        instruction: reviewCache.instruction,
        provider: reviewCache.provider,
        model: reviewCache.model,
        fallbackFrom: reviewCache.fallbackFrom,
        stale: reviewCache.stale,
      });
      materializeChanges(cachedChanges, { statusById: cachedStatus, keepNumbers: true });
      return;
    }
    reviewCache = null;

    if (!text.trim()) {
      review.empty = true;
      review.error = 'Diese Notiz ist leer – es gibt nichts zu überarbeiten.';
      return;
    }
    if (text.length > NOTE_REVIEW_INPUT_LIMIT) {
      review.error = 'Die Notiz ist für eine Überarbeitung in einem Schritt zu lang.';
      return;
    }
    await requestReview();
  }

  async function requestReview({ retry = false } = {}) {
    const ed = editor.value;
    if (!ed || !review.open || review.loading) return;
    if (!retry) reviewRetried = false;
    const current = flattenReviewDoc(ed.state.doc);
    review.baseText = current.text;
    baseMap = current.map;
    review.stale = false;
    review.preview = '';
    review.changes = [];
    review.status = {};
    review.focusId = null;
    review.hoverId = null;
    review.error = '';
    review.provider = '';
    review.model = '';
    review.fallbackFrom = '';
    review.empty = false;
    clearReviewDecorations(ed);
    if (!current.text.trim() || current.text.length > NOTE_REVIEW_INPUT_LIMIT) {
      review.error = !current.text.trim()
        ? 'Diese Notiz ist leer – es gibt nichts zu überarbeiten.'
        : 'Die Notiz ist für eine Überarbeitung in einem Schritt zu lang.';
      return;
    }
    review.loading = true;

    const request = requests.begin();
    const noteId = props.noteId;
    let needsRetry = false;
    try {
      await stream({
        note_text: review.baseText,
        note_structure: reviewStructureContext(ed.state.doc),
        extra_instruction: review.instruction.trim(),
        retry,
      }, {
        signal: request.signal,
        onEvent: (event) => {
          if (!request.isCurrent()) return;
          if (event.type === 'meta') {
            review.provider = event.provider || '';
            review.model = event.model || '';
            review.fallbackFrom = event.fallback_from || '';
          } else if (event.type === 'delta') {
            review.preview += event.text || '';
          }
        },
      });
      if (!request.isCurrent() || props.noteId !== noteId) return;
      const parsed = finishReview();
      // Ein einmaliger stiller Neuversuch fängt gelegentlich unsauberes JSON ab,
      // bevor der Nutzer überhaupt einen Fehler sieht.
      if (!parsed.ok && !reviewRetried) needsRetry = true;
      else if (!parsed.ok) {
        review.error = parsed.error || 'Die Antwort ließ sich nicht sicher auswerten. Bitte erneut versuchen.';
      }
    } catch (error) {
      if (request.isCurrent() && error?.name !== 'AbortError' && review.open) {
        if (error?.code === 'review_incomplete' && !reviewRetried) needsRetry = true;
        else review.error = error?.message || 'Überarbeitung fehlgeschlagen.';
      }
    } finally {
      // `loading` IMMER lösen, sonst blockiert der Guard einen folgenden
      // (Retry-)Aufruf und der Ladeschirm bleibt für immer stehen. Der Retry
      // setzt `loading` synchron sofort wieder auf true – kein Flackern.
      if (request.isCurrent()) {
        review.loading = false;
        if (needsRetry) {
          reviewRetried = true;
          void requestReview({ retry: true });
        }
      }
    }
  }

  // Löst die (geparsten, zwischengespeicherten oder verbleibenden) Verbesserungen
  // gegen das aktuelle Dokument auf und übernimmt sie in den Zustand.
  // `statusById` erhält frühere Entscheidungen; `keepNumbers` bewahrt die einmal
  // vergebenen Ziffern (nach Annehmen/Wiederherstellen wird NICHT neu numeriert).
  function materializeChanges(rawChanges, { statusById = null, keepNumbers = false } = {}) {
    const ed = editor.value;
    if (!ed) return 0;
    // Anchor → Zeichenbereich → Editor-Position, dann nur auffindbare behalten.
    const located = resolveReviewAnchors(review.baseText, rawChanges);
    const positioned = resolveReviewPositions(ed.state.doc, baseMap, located).filter((c) => c.found && buildReviewEdit(c));
    positioned.sort((a, b) => a.from - b.from);
    if (!keepNumbers) positioned.forEach((c, index) => { c.number = index + 1; });
    review.changes = positioned;
    review.status = Object.fromEntries(positioned.map((c) => [
      c.id,
      statusById && statusById[c.id] === 'rejected' ? 'rejected' : 'open',
    ]));
    review.empty = positioned.length === 0;
    review.focusId = null;
    review.hoverId = null;
    syncDecorations();
    return positioned.length;
  }

  function finishReview() {
    const ed = editor.value;
    if (!ed) return { ok: false, error: '' };
    const { ok, changes, error } = parseReviewOutput(review.preview);
    if (!ok) {
      return { ok: false, error };
    }
    const count = materializeChanges(changes);
    if (!count) {
      review.error = changes.length
        ? 'Die Verbesserungen ließen sich der Notiz nicht sicher zuordnen.'
        : '';
    }
    return { ok: true, error: '' };
  }

  // Löst die verbleibenden Verbesserungen nach einer Textänderung neu gegen das
  // Dokument auf (Positionen verschieben sich); Ziffern + Entscheidungen bleiben.
  function rematerializeRemaining(remaining, statusById) {
    const ed = editor.value;
    if (!ed) return;
    const { text, map } = flattenReviewDoc(ed.state.doc);
    review.baseText = text;
    baseMap = map;
    materializeChanges(remaining, { statusById, keepNumbers: true });
  }

  // Annehmen: die einzelne Verbesserung SOFORT in die Notiz schreiben (eigener
  // Undo-Schritt) und aus der Liste entfernen; der Rest wird neu aufgelöst.
  function acceptChange(id) {
    const ed = editor.value;
    if (!ed || ed.isDestroyed || review.loading) return;
    const change = review.changes.find((c) => c.id === id);
    if (!change || !change.found) return;
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
        applyingReviewEdit = true;
        try { applyReviewEdits(ed, edits); } finally { applyingReviewEdit = false; }
        onCheckpoint('ai');
      }
    }
    reviewCache = null; // der Text hat sich geändert
    rematerializeRemaining(others, statusById);
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
    if (review.loading) return;
    review.instructionOpen = false;
    void requestReview();
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
  watch(() => props.noteId, discardReview);

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
