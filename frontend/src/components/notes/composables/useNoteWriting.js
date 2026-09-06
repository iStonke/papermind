import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { createNoteAIRequest } from './noteAIRequest.js';
import { streamNoteText } from '../../../api/notes.js';
import { posToDOMRect } from '@tiptap/vue-3';
import { NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT } from '../../../constants/promptDefaults.js';
import { noteAITextForCodeBlock, noteMarkdownToTipTap } from '../../../utils/noteMarkdown.js';

export function useNoteWriting({
  editor,
  surfaceEl,
  props,
  overlays,
  clampMenuLeft,
  onCheckpoint,
  stream = streamNoteText,
}) {
  const requests = createNoteAIRequest();
  const aiToolbarInputEl = ref(null);
  const aiPromptInputEl = ref(null);
  const aiOptionsButtonEl = ref(null);
  const aiOptionsOpen = ref(false);
  const aiOptionsLeft = ref(0);
  const AI_PROMPT_WIDTH = 390;
  const AI_LENGTH_OPTIONS = Object.freeze([
    { label: 'Automatisch', lineHint: 'nach Prompt', instruction: '' },
    { label: 'Kurz', lineHint: 'ca. 1–3 Zeilen', instruction: 'Kurz antworten: ungefähr 1–3 Zeilen.' },
    { label: 'Mittel', lineHint: 'ca. 4–8 Zeilen', instruction: 'In mittlerer Länge antworten: ungefähr 4–8 Zeilen.' },
    { label: 'Lang', lineHint: 'ca. 9–16 Zeilen', instruction: 'Lang antworten: ungefähr 9–16 Zeilen mit allen relevanten Details.' },
  ]);
  const visibleAIPromptSuggestions = computed(() => (
    Array.isArray(props.aiPromptSuggestions)
      ? props.aiPromptSuggestions
        .filter((suggestion) => typeof suggestion === 'string')
        .map((suggestion) => suggestion.replace(/\s+/g, ' ').trim())
        .filter(Boolean)
        .slice(0, 6)
      : [...NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT]
  ));
  const aiPrompt = reactive({
    open: false,
    presentation: 'toolbar',
    mode: 'context',
    instruction: '',
    lengthLevel: 0,
    contextScope: 'before',
    generatedInstruction: '',
    preview: '',
    error: '',
    loading: false,
    provider: '',
    model: '',
    fallbackFrom: '',
    anchorPos: null,
    selectionFrom: null,
    selectionTo: null,
    selectedText: '',
    targetContainerType: '',
    targetContainerFrom: null,
    targetContainerTo: null,
    targetReplaceFrom: null,
    targetReplaceTo: null,
    style: {},
  });
  const aiSelectionTooLong = computed(() => (
    aiPrompt.mode === 'selection' && aiPrompt.selectedText.length > 8000
  ));
  const activeAILengthOption = computed(() => (
    AI_LENGTH_OPTIONS[aiPrompt.lengthLevel] || AI_LENGTH_OPTIONS[0]
  ));
  const aiContextLabel = computed(() => (
    aiPrompt.mode === 'selection'
      ? `Kontext: nur Auswahl · ${aiPrompt.selectedText.length.toLocaleString('de-DE')} Zeichen`
      : 'Kontext: Notiztext bis zum Cursor'
  ));

  const DIRECT_AI_CONTAINER_TYPES = new Set([
    'callout',
    'tableCell',
    'tableHeader',
    'blockquote',
    'codeBlock',
  ]);

  function directAIContainerAtPosition(ed, position) {
    const safePosition = Math.max(0, Math.min(position, ed.state.doc.content.size));
    const $position = ed.state.doc.resolve(safePosition);
    for (let depth = $position.depth; depth > 0; depth -= 1) {
      const type = $position.node(depth).type.name;
      if (!DIRECT_AI_CONTAINER_TYPES.has(type)) continue;
      return {
        type,
        from: $position.before(depth),
        to: $position.after(depth),
      };
    }
    return null;
  }

  function directAITargetForSelection(ed, selection) {
    const selectedNodeType = selection.node?.type.name;
    if (DIRECT_AI_CONTAINER_TYPES.has(selectedNodeType)) {
      return {
        type: selectedNodeType,
        from: selection.from,
        to: selection.from + selection.node.nodeSize,
        anchorPos: selection.from + selection.node.nodeSize - 1,
        nodeSelected: true,
      };
    }
    const start = directAIContainerAtPosition(ed, selection.from);
    if (!start) return null;
    const end = directAIContainerAtPosition(
      ed,
      selection.empty ? selection.from : Math.max(selection.from, selection.to - 1),
    );
    if (!end || end.type !== start.type || end.from !== start.from) return null;
    return { ...start, anchorPos: selection.to, nodeSelected: false };
  }

  function emptyParagraphRangeAtPosition(ed, position) {
    const safePosition = Math.max(0, Math.min(position, ed.state.doc.content.size));
    const $position = ed.state.doc.resolve(safePosition);
    if (
      $position.depth < 1
      || $position.parent.type.name !== 'paragraph'
      || $position.parent.content.size > 0
    ) return null;
    return {
      from: $position.before($position.depth),
      to: $position.after($position.depth),
    };
  }

  function positionAIPrompt() {
    const ed = editor.value;
    const surface = surfaceEl.value;
    if (!ed || !surface) return;
    const position = Math.min(aiPrompt.anchorPos ?? ed.state.selection.from, ed.state.doc.content.size);
    const rect = posToDOMRect(ed.view, position, position);
    const box = surface.getBoundingClientRect();
    aiPrompt.style = {
      left: `${clampMenuLeft(rect.left - box.left, box.width, AI_PROMPT_WIDTH)}px`,
      top: `${rect.bottom - box.top + 4}px`,
    };
  }

  function prepareAIPromptTarget(presentation = 'toolbar', { resetInstruction = false } = {}) {
    const ed = editor.value;
    if (!ed || aiPrompt.loading) return;
    // "Schreibmarke" = ein Cursor im Editor. Wird der Toolbar-Prompt geöffnet, ohne
    // dass der Editor den Fokus hat, gibt es keine Schreibmarke – der Text kommt dann
    // ans Notizende statt an die vom Editor gehaltene Standard-(Start-)Position.
    const hasCaret = presentation !== 'toolbar' || ed.view.hasFocus();
    const selection = ed.state.selection;
    const { from, to, empty } = selection;
    const directTarget = hasCaret ? directAITargetForSelection(ed, selection) : null;
    const selectedText = !hasCaret || empty || directTarget?.nodeSelected
      ? ''
      : ed.state.doc.textBetween(from, to, '\n', '\n').trim();
    aiPrompt.mode = selectedText ? 'selection' : 'context';
    aiPrompt.anchorPos = hasCaret
      ? (directTarget?.anchorPos ?? (selectedText ? to : from))
      : ed.state.doc.content.size;
    aiPrompt.selectionFrom = selectedText ? from : null;
    aiPrompt.selectionTo = selectedText ? to : null;
    aiPrompt.selectedText = selectedText;
    if (presentation === 'toolbar') aiPrompt.contextScope = selectedText ? 'selection' : 'before';
    aiPrompt.targetContainerType = directTarget?.type ?? '';
    aiPrompt.targetContainerFrom = directTarget?.from ?? null;
    aiPrompt.targetContainerTo = directTarget?.to ?? null;
    const emptyTargetRange = directTarget && !selectedText && !directTarget.nodeSelected
      ? emptyParagraphRangeAtPosition(ed, aiPrompt.anchorPos)
      : null;
    aiPrompt.targetReplaceFrom = emptyTargetRange?.from ?? null;
    aiPrompt.targetReplaceTo = emptyTargetRange?.to ?? null;
    aiPrompt.presentation = presentation;
    if (resetInstruction) aiPrompt.instruction = '';
    aiPrompt.generatedInstruction = '';
    aiPrompt.preview = '';
    aiPrompt.error = selectedText.length > 8000
      ? 'Die Auswahl ist zu lang. Bitte höchstens 8.000 Zeichen markieren.'
      : '';
    aiPrompt.provider = '';
    aiPrompt.model = '';
    aiPrompt.fallbackFrom = '';
    aiPrompt.open = true;
    overlays.open('writing');
  }

  function prepareToolbarAIPromptTarget() {
    // Preserve the captured cursor/selection while moving between prompt and options.
    if (aiPrompt.open && aiPrompt.presentation === 'toolbar' && !editor.value?.view.hasFocus()) return;
    prepareAIPromptTarget('toolbar');
  }

  function ensureToolbarAIPromptTarget() {
    if (!aiPrompt.open || aiPrompt.presentation !== 'toolbar') prepareToolbarAIPromptTarget();
  }

  function toggleAIOptions() {
    ensureToolbarAIPromptTarget();
    overlays.open('writing');
    const left = aiOptionsButtonEl.value?.getBoundingClientRect().left || 0;
    const width = Math.min(310, window.innerWidth - 40);
    aiOptionsLeft.value = Math.max(20 - left, Math.min(0, window.innerWidth - 20 - left - width));
    aiOptionsOpen.value = !aiOptionsOpen.value;
  }

  function closeAIOptions() {
    aiOptionsOpen.value = false;
    nextTick(() => aiOptionsButtonEl.value?.focus());
  }

  function openAIPrompt() {
    aiOptionsOpen.value = false;
    prepareAIPromptTarget('dialog', { resetInstruction: true });
    positionAIPrompt();
    nextTick(() => aiPromptInputEl.value?.focus());
  }

  function closeAIPrompt() {
    aiOptionsOpen.value = false;
    requests.cancel();
    aiPrompt.open = false;
    aiPrompt.presentation = 'toolbar';
    aiPrompt.loading = false;
    aiPrompt.instruction = '';
    aiPrompt.preview = '';
    aiPrompt.error = '';
    aiPrompt.generatedInstruction = '';
    aiPrompt.anchorPos = null;
    aiPrompt.selectedText = '';
    aiPrompt.selectionFrom = null;
    aiPrompt.selectionTo = null;
    aiPrompt.targetContainerType = '';
    aiPrompt.targetContainerFrom = null;
    aiPrompt.targetContainerTo = null;
    aiPrompt.targetReplaceFrom = null;
    aiPrompt.targetReplaceTo = null;
    aiPrompt.style = {};
  }

  function applyAIPromptSuggestion(suggestion) {
    aiPrompt.instruction = suggestion;
    nextTick(() => aiPromptInputEl.value?.focus());
  }

  function noteContextBeforeAnchor(ed) {
    const to = Math.min(aiPrompt.anchorPos ?? ed.state.selection.from, ed.state.doc.content.size);
    return ed.state.doc.textBetween(0, to, '\n', '\n').slice(-12000);
  }

  function aiBlockAttrs() {
    const prompt = aiPrompt.generatedInstruction || aiPrompt.instruction.trim();
    return {
      text: aiPrompt.preview.trim(),
      prompt,
      provider: aiPrompt.provider,
      model: aiPrompt.model,
      generatedAt: new Date().toISOString(),
      sources: [],
      stale: false,
    };
  }

  function selectionSnapshotIsCurrent(ed) {
    const { selectionFrom: from, selectionTo: to, selectedText } = aiPrompt;
    if (!Number.isInteger(from) || !Number.isInteger(to) || from >= to || to > ed.state.doc.content.size) {
      return false;
    }
    return ed.state.doc.textBetween(from, to, '\n', '\n').trim() === selectedText;
  }

  function directAITargetIsCurrent(ed) {
    const {
      targetContainerType: type,
      targetContainerFrom: from,
      targetContainerTo: to,
    } = aiPrompt;
    if (!DIRECT_AI_CONTAINER_TYPES.has(type) || !Number.isInteger(from) || !Number.isInteger(to)) {
      return false;
    }
    const node = ed.state.doc.nodeAt(from);
    return node?.type.name === type && from + node.nodeSize === to;
  }

  function directAIContent() {
    if (aiPrompt.targetContainerType === 'codeBlock') {
      const text = noteAITextForCodeBlock(aiPrompt.preview);
      return text ? [{ type: 'text', text }] : [];
    }
    return noteMarkdownToTipTap(aiPrompt.preview.trim());
  }

  function insertDirectAIResult(ed, { from = null, to = null } = {}) {
    if (!directAITargetIsCurrent(ed)) {
      const targetLabel = {
        callout: 'Der Hinweisblock',
        tableCell: 'Die Tabellenzelle',
        tableHeader: 'Die Tabellenzelle',
        blockquote: 'Das Zitat',
        codeBlock: 'Der Codeblock',
      }[aiPrompt.targetContainerType] || 'Der Zielbereich';
      aiPrompt.error = `${targetLabel} hat sich geändert. Bitte den KI-Prompt erneut starten.`;
      return false;
    }
    const content = directAIContent();
    if (!content.length) {
      aiPrompt.error = 'Das Modell hat keinen einfügbaren Text erzeugt.';
      return false;
    }

    const chain = ed.chain().focus();
    if (Number.isInteger(from) && Number.isInteger(to)) {
      chain.insertContentAt({ from, to }, content, { updateSelection: true });
    } else {
      const insertionPos = Math.min(aiPrompt.anchorPos, ed.state.doc.content.size);
      chain.setTextSelection(insertionPos).insertContent(content);
    }
    chain.scrollIntoView().run();
    onCheckpoint('ai');
    closeAIPrompt();
    return true;
  }

  function applySelectionAIResult(action) {
    const ed = editor.value;
    if (!ed || aiPrompt.mode !== 'selection' || !aiPrompt.preview.trim()) return;
    if (!selectionSnapshotIsCurrent(ed)) {
      aiPrompt.error = 'Die Textauswahl hat sich geändert. Bitte schließen und erneut auswählen.';
      return;
    }

    const from = aiPrompt.selectionFrom;
    const to = aiPrompt.selectionTo;
    if (Number.isInteger(aiPrompt.targetContainerFrom)) {
      insertDirectAIResult(ed, action === 'replace' ? { from, to } : { from: to, to });
      return;
    }
    const attrs = aiBlockAttrs();
    const chain = ed.chain().focus();
    if (action === 'replace') {
      chain.insertContentAt({ from, to }, { type: 'aiBlock', attrs });
    } else {
      chain.setTextSelection(to).insertAiBlock(attrs);
    }
    chain.focus('end').scrollIntoView().run();
    onCheckpoint('ai');
    closeAIPrompt();
  }

  async function generateAIText() {
    const ed = editor.value;
    if (!aiPrompt.open) prepareToolbarAIPromptTarget();
    const instruction = aiPrompt.instruction.trim();
    if (!ed || !instruction || aiPrompt.loading || aiSelectionTooLong.value) return;

    const wholeNote = aiPrompt.presentation === 'toolbar' && aiPrompt.contextScope === 'note';
    const contextText = wholeNote ? ed.getText() : noteContextBeforeAnchor(ed);
    if (wholeNote && contextText.length > 12000) {
      aiPrompt.error = 'Die ganze Notiz ist zu lang (max. 12.000 Zeichen). Bitte einen kleineren Kontext wählen.';
      return;
    }
    aiOptionsOpen.value = false;

    aiPrompt.loading = true;
    aiPrompt.generatedInstruction = instruction;
    aiPrompt.preview = '';
    aiPrompt.error = '';
    aiPrompt.provider = '';
    aiPrompt.model = '';
    aiPrompt.fallbackFrom = '';
    const request = requests.begin();
    const noteId = props.noteId;

    try {
      await stream({
        instruction,
        length_instruction: activeAILengthOption.value.instruction,
        note_context: aiPrompt.presentation === 'toolbar'
          ? (aiPrompt.contextScope === 'selection' ? '' : contextText)
          : (aiPrompt.mode === 'selection' ? '' : noteContextBeforeAnchor(ed)),
        context_scope: wholeNote ? 'note' : 'before',
        selected_text: aiPrompt.mode === 'selection' ? aiPrompt.selectedText : '',
        document_context: '',
      }, {
        signal: request.signal,
        onEvent: (event) => {
          if (!request.isCurrent()) return;
          if (event.type === 'meta') {
            aiPrompt.provider = event.provider || '';
            aiPrompt.model = event.model || '';
            aiPrompt.fallbackFrom = event.fallback_from || '';
          } else if (event.type === 'delta') {
            aiPrompt.preview += event.text || '';
          }
        },
      });

      if (!request.isCurrent() || editor.value !== ed || ed.isDestroyed || props.noteId !== noteId) return;
      const text = aiPrompt.preview.trim();
      if (!text) throw new Error('Das Modell hat keinen Text erzeugt.');
      if (aiPrompt.mode === 'selection') {
        if (!selectionSnapshotIsCurrent(ed)) {
          throw new Error('Die Textauswahl hat sich geändert. Bitte schließen und erneut auswählen.');
        }
        if (aiPrompt.presentation === 'dialog') return;
        applySelectionAIResult('replace');
        return;
      }
      if (Number.isInteger(aiPrompt.targetContainerFrom)) {
        const replaceEmptyParagraph = (
          Number.isInteger(aiPrompt.targetReplaceFrom)
          && Number.isInteger(aiPrompt.targetReplaceTo)
          && ed.state.doc.nodeAt(aiPrompt.targetReplaceFrom)?.type.name === 'paragraph'
          && ed.state.doc.nodeAt(aiPrompt.targetReplaceFrom)?.content.size === 0
        );
        insertDirectAIResult(ed, replaceEmptyParagraph
          ? { from: aiPrompt.targetReplaceFrom, to: aiPrompt.targetReplaceTo }
          : {});
        return;
      }
      const insertionPos = Math.min(
        aiPrompt.anchorPos ?? ed.state.selection.from,
        ed.state.doc.content.size,
      );
      ed.chain()
        .focus()
        .setTextSelection(insertionPos)
        .insertAiBlock({ ...aiBlockAttrs() })
        .focus('end')
        .scrollIntoView()
        .run();
      onCheckpoint('ai');
      closeAIPrompt();
    } catch (error) {
      if (request.isCurrent() && error?.name !== 'AbortError' && aiPrompt.open) {
        aiPrompt.error = error?.message || 'Text konnte nicht generiert werden.';
      }
    } finally {
      if (request.isCurrent()) aiPrompt.loading = false;
    }
  }

  overlays.register('writing', closeAIPrompt);
  onBeforeUnmount(closeAIPrompt);
  watch(() => props.noteId, closeAIPrompt);
  return {
    editor,
    aiToolbarInputEl,
    aiPromptInputEl,
    aiOptionsButtonEl,
    aiOptionsOpen,
    aiOptionsLeft,
    AI_LENGTH_OPTIONS,
    aiPrompt,
    aiSelectionTooLong,
    activeAILengthOption,
    aiContextLabel,
    visibleAIPromptSuggestions,
    prepareToolbarAIPromptTarget,
    ensureToolbarAIPromptTarget,
    toggleAIOptions,
    closeAIOptions,
    openAIPrompt,
    closeAIPrompt,
    applyAIPromptSuggestion,
    applySelectionAIResult,
    generateAIText,
    positionAIPrompt,
  };
}
