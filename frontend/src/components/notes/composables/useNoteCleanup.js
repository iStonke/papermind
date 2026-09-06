import { computed, nextTick, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue';
import { createNoteAIRequest } from './noteAIRequest.js';
import { streamNoteText } from '../../../api/notes.js';
import { hideCleanupReviewAnchor, showCleanupReviewAnchor } from '../extensions/cleanupReviewAnchor.js';
import { CLEANUP_INPUT_LIMIT, CLEANUP_INSTRUCTION, diffCleanupText, formatCleanupInput, parseCleanupOutput, stripCleanupMarks } from '../../../utils/noteCleanup.js';

export function useNoteCleanup({ editor, props, overlays, onCheckpoint, stream = streamNoteText }) {
const requests = createNoteAIRequest();
const cleanupAnchorEl = shallowRef(null);
const cleanupViews = Object.freeze([
  { value: 'original', label: 'Original' },
  { value: 'diff', label: 'Vergleich' },
  { value: 'clean', label: 'Bereinigt' },
]);
const cleanup = reactive({
  open: false,
  loading: false,
  scope: 'note',
  targets: [],
  preview: '',
  draftBlocks: [],
  view: 'diff',
  instructionOpen: false,
  instruction: '',
  selectionFrom: null,
  selectionTo: null,
  error: '',
  provider: '',
  model: '',
  fallbackFrom: '',
  anchorPos: null,
});
const cleanupRestore = reactive({ open: false });

const cleanupOriginalText = computed(() => cleanup.targets.map((target) => target.text).join('\n\n'));
const cleanupDraftText = computed(() => cleanup.draftBlocks.join('\n\n'));
const cleanupDiffParts = computed(() => diffCleanupText(cleanupOriginalText.value, cleanupDraftText.value));
const cleanupCanApply = computed(() => (
  cleanup.draftBlocks.length === cleanup.targets.length
  && cleanup.draftBlocks.every((block) => String(block || '').trim())
));

// Bei einer Auswahl werden alle berührten Textblöcke separat erfasst. Dadurch
// bleiben Überschriften, Listen, Aufgaben, Zitate, Hinweisblöcke und Tabellen-
// zellen strukturell unverändert; ersetzt wird ausschließlich ihr Textinhalt.
// Codeblöcke werden bewusst ausgelassen, weil sprachliches Glätten dort Code
// beschädigen könnte. Ohne Auswahl gilt der Befehl weiterhin nur für lose
// Fließtext-Absätze der Notiz.
function collectCleanupTargets(ed) {
  const selection = ed.state.selection;
  const { from, to, empty } = selection;
  const scoped = !empty;
  const targets = [];
  ed.state.doc.descendants((node, pos, parent) => {
    if (scoped && node.isTextblock) {
      if (node.type.name === 'codeBlock') return false;
      const contentFrom = pos + 1;
      const contentTo = pos + node.nodeSize - 1;
      const targetFrom = Math.max(from, contentFrom);
      const targetTo = Math.min(to, contentTo);
      if (targetTo > targetFrom) {
        const text = ed.state.doc.textBetween(targetFrom, targetTo, '\n', '\n');
        if (text.trim()) targets.push({ from: targetFrom, to: targetTo, text, kind: 'range' });
      }
      return false;
    }
    if (!scoped && parent?.type.name === 'doc' && node.type.name === 'paragraph') {
      const text = node.textContent.trim();
      if (text) targets.push({
        from: pos + 1,
        to: pos + node.nodeSize - 1,
        text,
        kind: 'range',
      });
      return false;
    }
    return undefined;
  });
  return {
    targets,
    scope: scoped ? 'selection' : 'note',
    selectionFrom: scoped ? from : null,
    selectionTo: scoped ? to : null,
  };
}

function cleanupReviewPosition(ed, targets, selectionTo) {
  const position = Math.min(
    selectionTo ?? targets.at(-1)?.to ?? ed.state.selection.to,
    ed.state.doc.content.size,
  );
  const $position = ed.state.doc.resolve(position);
  return $position.depth > 0 ? $position.after(1) : position;
}

function resetCleanupState() {
  requests.cancel();
  cleanup.open = false;
  cleanup.loading = false;
  cleanup.preview = '';
  cleanup.draftBlocks = [];
  cleanup.view = 'diff';
  cleanup.instructionOpen = false;
  cleanup.instruction = '';
  cleanup.selectionFrom = null;
  cleanup.selectionTo = null;
  cleanup.error = '';
  cleanup.targets = [];
  cleanup.anchorPos = null;
}

function closeCleanup() {
  const ed = editor.value;
  cleanupRestore.open = false;
  resetCleanupState();
  if (ed) hideCleanupReviewAnchor(ed);
}

async function startCleanup() {
  const ed = editor.value;
  if (!ed || !props.aiAvailable || cleanup.loading) return;
  const { targets, scope, selectionFrom, selectionTo } = collectCleanupTargets(ed);

  overlays.open('cleanup');

  cleanup.open = true;
  cleanup.scope = scope;
  cleanup.targets = targets;
  cleanup.preview = '';
  cleanup.draftBlocks = [];
  cleanup.view = 'diff';
  cleanup.instructionOpen = false;
  cleanup.instruction = '';
  cleanup.selectionFrom = selectionFrom;
  cleanup.selectionTo = selectionTo;
  cleanup.error = '';
  cleanup.provider = '';
  cleanup.model = '';
  cleanup.fallbackFrom = '';
  cleanup.anchorPos = cleanupReviewPosition(ed, targets, selectionTo);
  cleanupRestore.open = false;
  showCleanupReviewAnchor(ed, cleanup.anchorPos);
  // Die ursprüngliche Browser-Auswahl würde auch den eingefügten Prüfbereich
  // blau übermalen. Der exakte Bereich ist oben bereits sicher gespeichert;
  // visuell wird die Auswahl deshalb auf ihr Ende eingeklappt.
  if (scope === 'selection' && Number.isInteger(selectionTo)) {
    ed.commands.setTextSelection(selectionTo);
  }

  if (!targets.length) {
    cleanup.error = 'Kein bereinigbarer Text gefunden. Codeblöcke bleiben zum Schutz ihres Inhalts unverändert.';
    return;
  }
  const payload = formatCleanupInput(targets.map((target) => target.text));
  if (payload.length > CLEANUP_INPUT_LIMIT) {
    cleanup.error = 'Der Text ist für das Aufräumen in einem Schritt zu lang. Bitte einen Abschnitt markieren und erneut aufräumen.';
    return;
  }

  await requestCleanup();
}

async function requestCleanup() {
  if (!cleanup.open || !cleanup.targets.length || cleanup.loading) return;
  const payload = formatCleanupInput(cleanup.targets.map((target) => target.text));
  const extraInstruction = cleanup.instruction.trim();
  const instruction = extraInstruction
    ? `${CLEANUP_INSTRUCTION}\n\nZusätzliche Anweisung des Nutzers: ${extraInstruction}`
    : CLEANUP_INSTRUCTION;
  cleanup.preview = '';
  cleanup.draftBlocks = [];
  cleanup.error = '';
  cleanup.provider = '';
  cleanup.model = '';
  cleanup.fallbackFrom = '';
  cleanup.loading = true;
  const request = requests.begin();
  const noteId = props.noteId;
  try {
    await stream({
      instruction,
      length_instruction: '',
      note_context: '',
      selected_text: payload,
      document_context: '',
    }, {
      signal: request.signal,
      onEvent: (event) => {
        if (!request.isCurrent()) return;
        if (event.type === 'meta') {
          cleanup.provider = event.provider || '';
          cleanup.model = event.model || '';
          cleanup.fallbackFrom = event.fallback_from || '';
        } else if (event.type === 'delta') {
          cleanup.preview += event.text || '';
        }
      },
    });
    if (!request.isCurrent() || props.noteId !== noteId) return;
    const { ok, blocks } = parseCleanupOutput(cleanup.preview, cleanup.targets.length);
    if (!ok || !stripCleanupMarks(cleanup.preview)) {
      cleanup.error = 'Das Ergebnis ließ sich nicht sicher zuordnen. Bitte erneut aufräumen oder einen kleineren Abschnitt markieren.';
    } else {
      cleanup.draftBlocks = blocks;
      cleanup.view = 'diff';
    }
  } catch (error) {
    if (request.isCurrent() && error?.name !== 'AbortError' && cleanup.open) {
      cleanup.error = error?.message || 'Aufräumen fehlgeschlagen.';
    }
  } finally {
    if (request.isCurrent()) cleanup.loading = false;
  }
}

function regenerateCleanup() {
  if (cleanup.loading) return;
  cleanup.instructionOpen = false;
  void requestCleanup();
}

function discardCleanup() {
  const ed = editor.value;
  const from = cleanup.selectionFrom;
  const to = cleanup.selectionTo;
  closeCleanup();
  if (ed && Number.isInteger(from) && Number.isInteger(to) && from < to) {
    ed.chain().focus().setTextSelection({ from, to }).run();
  }
}

function applyCleanup() {
  const ed = editor.value;
  if (!ed || cleanup.loading || !cleanup.targets.length || !cleanupCanApply.value) return;
  // Haben sich die Ziele seit dem Sammeln verschoben, lieber abbrechen als an
  // einer falschen Stelle zu ersetzen.
  const stillValid = cleanup.targets.every((target) => {
    return target.to <= ed.state.doc.content.size
      && ed.state.doc.textBetween(target.from, target.to, '\n', '\n') === target.text;
  });
  if (!stillValid) {
    cleanup.error = 'Die Notiz hat sich geändert. Bitte das Aufräumen erneut starten.';
    return;
  }
  // Von hinten nach vorn ersetzen, damit die früheren Positionen gültig bleiben.
  const ordered = cleanup.targets
    .map((target, index) => ({ ...target, cleaned: cleanup.draftBlocks[index].trim() }))
    .sort((a, b) => b.from - a.from);
  const chain = ed.chain().focus();
  ordered.forEach((target) => {
    chain.insertContentAt(
      { from: target.from, to: target.to },
      { type: 'text', text: target.cleaned },
    );
  });
  chain.scrollIntoView().run();
  onCheckpoint('ai');
  cleanup.open = false;
  cleanupRestore.open = true;
}

function restoreCleanupOriginal() {
  const ed = editor.value;
  if (!ed) return;
  ed.commands.undo();
  cleanupRestore.open = false;
  resetCleanupState();
  hideCleanupReviewAnchor(ed);
}


overlays.register('cleanup', closeCleanup);
onBeforeUnmount(closeCleanup);
watch(() => props.noteId, closeCleanup);
return { editor, cleanup, cleanupRestore, cleanupAnchorEl, cleanupViews, cleanupOriginalText, cleanupDraftText, cleanupDiffParts, cleanupCanApply, closeCleanup, startCleanup, regenerateCleanup, discardCleanup, applyCleanup, restoreCleanupOriginal };
}
