<!--
  NoteEditor besitzt die gemeinsame TipTap-Instanz, synchronisiert Titel und
  Body-JSON und stellt Suche, Verlauf und Fokus für den Aufrufer bereit.
  Werkzeugleiste, KI-Funktionen und Einfügemenüs besitzen jeweils eigene
  Controller und Ansichten. Das Speichern übernimmt weiterhin der Aufrufer.
-->
<template>
  <div
    ref="rootEl"
    class="note-editor"
    :class="[
      { 'note-editor--workspace': workspace },
      `note-editor--width-${normalizedWritingWidth}`,
      `note-editor--spacing-${normalizedParagraphSpacing}`,
      `note-editor--font-${normalizedFontFamily}`,
    ]"
  >
    <input
      v-if="!workspace"
      ref="titleEl"
      class="note-editor__title"
      type="text"
      :value="title"
      :placeholder="titlePlaceholder"
      :spellcheck="spellcheckEnabled"
      @input="onTitleInput"
      @keydown.enter.prevent="focusBody"
    />

    <NoteEditorToolbar
      v-if="workspace"
      :controller="toolbar"
      :readonly="readonly"
      :toolbar-scrolled="toolbarScrolled"
    >

      <NoteWritingToolbar v-if="aiAvailable" :controller="writing" />
    </NoteEditorToolbar>

    <input
      ref="imageInputEl"
      class="note-editor__image-input"
      type="file"
      accept="image/jpeg,image/png,image/webp"
      multiple
      tabindex="-1"
      aria-hidden="true"
      @change="onImageInput"
    />

    <div
      ref="surfaceEl"
      class="note-editor__surface"
      @pointerdown="refocusEditorFromWhitespace"
      @pointermove.passive="trackTableHandle"
      @pointerleave="clearHoveredTable"
    >
      <div
        v-if="imageUploadCount > 0 || imageUploadMessage"
        class="note-editor__image-status"
        :class="{ 'is-error': imageUploadError }"
        role="status"
        aria-live="polite"
      >
        <span v-if="imageUploadCount > 0" class="note-editor__image-spinner" aria-hidden="true"></span>
        <v-icon v-else size="17">mdi-alert-circle-outline</v-icon>
        <span>{{ imageUploadCount > 0 ? imageUploadLabel : imageUploadMessage }}</span>
      </div>

      <div ref="writingEl" class="note-editor__writing">
        <editor-content :editor="editor" />

        <div
          v-if="workspace && editorEmpty"
          class="note-editor__empty-hint"
          :class="{ 'is-positioned': emptyHintPositioned }"
          :style="emptyHintStyle"
          aria-hidden="true"
        >
          <span class="note-editor__empty-hint-title">{{ placeholder }}</span>
          <span class="note-editor__empty-hint-detail">
            <kbd>/</kbd>
            <span>für Überschriften, Listen und weitere Blöcke</span>
          </span>
        </div>
      </div>

      <NoteTableMenu :controller="tables" />

      <!-- Auswahl-Formatierung -->
      <div
        v-if="editor && bubble.show"
        ref="bubbleEl"
        class="pm-float pm-bubble"
        :style="bubble.style"
        role="toolbar"
        aria-label="Formatierung"
      >
        <div class="pm-bubble__row">
          <button
            v-for="b in bubbleButtons"
            :key="b.key"
            type="button"
            class="pm-bubble__btn"
            :class="{ 'is-active': b.active(), 'is-ai': b.ai }"
            :title="b.label"
            :aria-label="b.label"
            @mousedown.prevent="b.run()"
          >
            <v-icon size="17">{{ b.icon }}</v-icon>
          </button>
        </div>
        <div
          v-if="bubbleHighlight.open"
          class="pm-bubble__swatches"
          role="menu"
          aria-label="Textmarkerfarbe"
        >
          <button
            v-for="color in NOTE_HIGHLIGHT_COLORS"
            :key="color.value"
            type="button"
            class="pm-bubble__swatch"
            :class="{ 'is-active': isTextHighlightActive(color.value) }"
            :style="{ '--pm-swatch': color.background }"
            :title="color.label"
            :aria-label="`Textmarker ${color.label}`"
            role="menuitemradio"
            :aria-checked="isTextHighlightActive(color.value) ? 'true' : 'false'"
            @mousedown.prevent="applyBubbleHighlight(color.value)"
          ></button>
          <button
            type="button"
            class="pm-bubble__swatch pm-bubble__swatch--remove"
            :disabled="!toolbarActive('highlight')"
            title="Markierung entfernen"
            aria-label="Markierung entfernen"
            @mousedown.prevent="removeBubbleHighlight()"
          ><v-icon size="14">mdi-eraser</v-icon></button>
        </div>
      </div>

      <!-- Klassischer externer Hyperlink. Interne PaperMind-Ziele bleiben
           bewusst dem [[Verweis]]-Element vorbehalten. -->
      <NoteLinkMenu :controller="links" />

      <div
        v-if="editor && slash.open && slashResults.length"
        ref="slashMenuEl"
        class="pm-float pm-slash pm-slash--commands"
        :style="slash.style"
        role="listbox"
        aria-label="Block einfügen"
      >
        <span
          class="pm-slash__selection"
          :class="{ 'is-visible': slash.selectionVisible }"
          :style="slash.selectionStyle"
          aria-hidden="true"
        ></span>
        <div class="pm-slash__hint">Block einfügen</div>
        <div
          v-for="group in slashGroups"
          :key="group.key"
          class="pm-slash__group"
          :class="{ 'is-frequent': group.key === 'frequent' }"
          :aria-label="group.label"
        >
          <div class="pm-slash__group-label">{{ group.label }}</div>
          <button
            v-for="entry in group.items"
            :key="entry.command.key"
            type="button"
            class="pm-slash__item"
            :class="{ 'is-active': entry.index === slash.index }"
            :data-slash-index="entry.index"
            role="option"
            :aria-selected="entry.index === slash.index"
            @mousemove="selectSlashIndex(entry.index)"
            @mousedown.prevent="runSlash(entry.command)"
          >
            <span class="pm-slash__chip">{{ entry.command.chip }}</span>
            <span class="pm-slash__text">
              <span class="pm-slash__label">{{ entry.command.label }}</span>
              <span class="pm-slash__desc">{{ entry.command.desc }}</span>
            </span>
          </button>
        </div>
      </div>

      <NoteReferencePicker :controller="references" />

      <!-- Vollständiger Dialog für explizite KI-Aufrufe am Text. Die dauerhaft
           sichtbare Toolbar-Zeile bleibt davon unabhängig kompakt. -->
      <NoteWritingPrompt :controller="writing" />

      <!-- Der Besen öffnet die Prüfung direkt im Textfluss. Die Dekoration setzt
           nur einen temporären Anker; Vorschlag und Original werden nie vor der
           ausdrücklichen Übernahme in den Dokumentinhalt geschrieben. -->
      <NoteCleanupReview :controller="cleaning" />

    </div>

    <div v-if="!workspace" class="note-editor__status">
      <span class="note-editor__save" :class="`is-${status}`">
        <span class="note-editor__dot"></span>
        {{ saveLabel }}
      </span>
      <span class="note-editor__count">{{ words }} {{ words === 1 ? 'Wort' : 'Wörter' }}</span>
    </div>


    <NoteShortcutsDialog ref="shortcutsDialogRef" @close="editor?.commands.focus()" />
  </div>
</template>

<script setup>
import NoteShortcutsDialog from './NoteShortcutsDialog.vue';
import NoteEditorToolbar from './NoteEditorToolbar.vue';
import { useNoteToolbar } from './composables/useNoteToolbar.js';
import NoteLinkMenu from './NoteLinkMenu.vue';
import NoteTableMenu from './NoteTableMenu.vue';
import NoteReferencePicker from './NoteReferencePicker.vue';
import { useNoteLinks } from './composables/useNoteLinks.js';
import { useNoteTables } from './composables/useNoteTables.js';
import { useNoteReferences } from './composables/useNoteReferences.js';
import NoteWritingToolbar from './NoteWritingToolbar.vue';
import NoteWritingPrompt from './NoteWritingPrompt.vue';
import NoteCleanupReview from './NoteCleanupReview.vue';
import { useNoteWriting } from './composables/useNoteWriting.js';
import { useNoteCleanup } from './composables/useNoteCleanup.js';
import { createNoteOverlayCoordinator } from './composables/noteOverlayCoordinator.js';
import { computed, inject, nextTick, onBeforeUnmount, onMounted, reactive, ref, toRaw, watch } from 'vue';
import { NOTE_AI_STREAM } from './composables/noteAIRequest.js';
import { NoteAIGeneration } from './extensions/aiGeneration.js';
import { EditorContent, useEditor, posToDOMRect } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import FileHandler from '@tiptap/extension-file-handler';
import Placeholder from '@tiptap/extension-placeholder';
import Typography from '@tiptap/extension-typography';
import TaskList from '@tiptap/extension-task-list';
import { PaperMindTaskItem } from './nodes/taskItemDue.js';
import { TableKit } from '@tiptap/extension-table';
import { isHistoryTransaction } from '@tiptap/pm/history';
import { TextSelection } from '@tiptap/pm/state';
import { DocumentChip } from './nodes/documentChip.js';
import { OcrQuote } from './nodes/ocrQuote.js';
import { AiBlock } from './nodes/aiBlock.js';
import { WikiLink } from './nodes/wikiLink.js';
import { Callout } from './nodes/callout.js';
import { LayoutColumn, PageLayout } from './nodes/pageLayout.js';
import { NoteHighlight } from './nodes/noteHighlight.js';
import { PaperMindDocument } from './nodes/noteDocument.js';
import { TemplateBox, TemplateField } from './nodes/templateBox.js';
import { NoteImage } from './nodes/noteImage.js';
import {
  HistoryFlash,
  clearHistoryFlash,
  historyChangedRange,
  showHistoryFlash,
} from './extensions/historyFlash.js';
import {
  NoteSearch,
  getNoteSearchState,
  setNoteSearch,
} from './extensions/noteSearch.js';
import {
  CleanupReviewAnchor,
  hideCleanupReviewAnchor,
} from './extensions/cleanupReviewAnchor.js';
import { MOCK_DOCUMENTS, mockLinkTargets } from './mockData.js';
import { NOTE_CALLOUT_OPTIONS } from '../../utils/noteCallouts.js';
import { NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT } from '../../constants/promptDefaults.js';
import { NOTE_TEMPLATE_PRESETS } from './nodes/noteTemplates.js';
import {
  NOTE_SLASH_USAGE_STORAGE_KEY,
  incrementNoteSlashUsage,
  mostUsedSlashCommands,
  parseNoteSlashUsage,
} from '../../utils/noteSlashUsage.js';
import { uploadNoteImage } from '../../api/notes.js';
import { NOTE_HIGHLIGHT_COLORS } from '../../utils/noteHighlights.js';
import { placeSelectionBubble } from '../../utils/noteBubblePosition.js';

const props = defineProps({
  /** Body als ProseMirror-JSON-Dokument (oder null für leer). */
  modelValue: { type: Object, default: null },
  /** Persistierte Notiz-ID für owner-scoped Bild-Uploads. */
  noteId: { type: String, default: null },
  title: { type: String, default: '' },
  titlePlaceholder: { type: String, default: 'Titel der Notiz' },
  placeholder: { type: String, default: 'Einfach losschreiben …' },
  /** 'idle' | 'saving' | 'saved' — nur Anzeige, Speichern macht der Aufrufer. */
  status: { type: String, default: 'idle' },
  /** Beim Mounten den Titel fokussieren (z. B. neue Notiz im Dialog). */
  autofocus: { type: Boolean, default: false },
  /** Eingebettete Workspace-Variante mit fester Formatleiste. */
  workspace: { type: Boolean, default: false },
  /** Maximale Zeilenlänge der Schreibfläche. */
  writingWidth: { type: String, default: 'comfortable' },
  /** Vertikaler Abstand zwischen Absätzen und anderen Textblöcken. */
  paragraphSpacing: { type: String, default: 'comfortable' },
  /** Einheitliche Schriftfamilie für Fließtext und Überschriften. */
  fontFamily: { type: String, default: 'sans' },
  /** Native Rechtschreibprüfung für Titel und Editorinhalt. */
  spellcheckEnabled: { type: Boolean, default: true },
  /** Inhalt anzeigen und auswählen, aber nicht verändern. */
  readonly: { type: Boolean, default: false },
  /** Nur bei vollständig nutzbarer Modell-/Zugangskonfiguration anzeigen. */
  aiAvailable: { type: Boolean, default: false },
  /** Konfigurierbare Schnellprompts im vollständigen KI-Dialog (maximal 6). */
  aiPromptSuggestions: {
    type: Array,
    default: () => [...NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT],
  },
  /** Echte Dokumente für /beleg (und /verweis-Ziele, falls keine linkTargets).
   *  Form: { id, label, type:'document', hint }. null → Mock-Daten (Prüfstand). */
  documentItems: { type: Array, default: null },
  /** Echte Verweis-Ziele für /verweis und [[…]]. null → aus documentItems bzw. Mock. */
  linkTargets: { type: Array, default: null },
  /** Benutzereigene Baustein-Vorlagen (Feldblöcke) fürs Slash-Menü. */
  blockTemplates: { type: Array, default: () => [] },
});

const emit = defineEmits([
  'update:modelValue',
  'update:title',
  'change',
  'word-count',
  'history-checkpoint',
  'note-search-state',
  'save-block-template',
  'image-upload-error',
]);

const overlays = createNoteOverlayCoordinator();
const surfaceEl = ref(null);
const writingEl = ref(null);
const titleEl = ref(null);
const shortcutsDialogRef = ref(null);
function openShortcuts() {
  openMenu.value = null;
  shortcutsDialogRef.value?.open();
}
const imageInputEl = ref(null);
const slashMenuEl = ref(null);
const bubbleEl = ref(null);
const words = ref(0);
const editorEmpty = ref(true);
const toolbarScrolled = ref(false);
const emptyHintPositioned = ref(false);
const emptyHintStyle = ref({ top: '0px', left: '0px' });
const normalizedWritingWidth = computed(() =>
  ['compact', 'comfortable', 'wide'].includes(props.writingWidth)
    ? props.writingWidth
    : 'comfortable'
);
const normalizedParagraphSpacing = computed(() =>
  ['compact', 'comfortable', 'spacious'].includes(props.paragraphSpacing)
    ? props.paragraphSpacing
    : 'comfortable'
);
const normalizedFontFamily = computed(() =>
  ['sans', 'serif', 'mono'].includes(props.fontFamily) ? props.fontFamily : 'sans'
);
let toolbarScrollContainer = null;
let toolbarScrollRestoreFrame = null;
let historyFlashTimer = null;
let emptyHintPositionFrame = null;
let emptyHintResizeObserver = null;
let imageUploadMessageTimer = null;

const NOTE_IMAGE_MIME_TYPES = Object.freeze(['image/jpeg', 'image/png', 'image/webp']);
const NOTE_IMAGE_UPLOAD_LIMIT = 8;
const imageUploadCount = ref(0);
const imageUploadMessage = ref('');
const imageUploadError = ref(false);
const imageUploadLabel = computed(() => (
  imageUploadCount.value === 1
    ? 'Bild wird eingefügt …'
    : `${imageUploadCount.value} Bilder werden eingefügt …`
));

/* ── Editor ──────────────────────────────────────────────────────────────── */
// Referenz auf das zuletzt selbst emittierte modelValue-JSON. Damit erkennt der
// modelValue-Watcher eine vom Editor SELBST ausgelöste Änderung an einem billigen
// Referenzvergleich, statt bei jedem Anschlag zweimal das komplette Dokument zu
// serialisieren (und dabei das reaktive Body-Objekt tief zu proxen).
let lastEmittedModelValue = null;
const editor = useEditor({
  content: props.modelValue || '',
  editable: !props.readonly,
  extensions: [
    StarterKit.configure({
      document: false,
      // Keine künstliche, blinkende Auswahl zwischen Blockelementen anzeigen.
      // Die normale Browser-Schreibmarke bleibt die einzige Cursoranzeige.
      gapcursor: false,
      // H1 bleibt für bestehende Notizen lesbar, wird aber nicht mehr als
      // Formatierungsaktion angeboten. Der Notiztitel übernimmt diese Ebene.
      heading: { levels: [1, 2, 3, 4] },
      link: {
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
        HTMLAttributes: { target: '_blank', rel: 'noopener noreferrer' },
      },
    }),
    PageLayout,
    LayoutColumn,
    NoteHighlight,
    PaperMindDocument,
    Placeholder.configure({ placeholder: props.placeholder }),
    Typography,
    TaskList,
    NoteAIGeneration,
    PaperMindTaskItem.configure({ nested: true }),
    TableKit.configure({
      table: {
        resizable: true,
        renderWrapper: true,
        lastColumnResizable: false,
        allowTableNodeSelection: true,
      },
    }),
    // PaperMind-eigene Bausteine (M1, gegen Mock-Daten).
    DocumentChip,
    OcrQuote,
    AiBlock,
    WikiLink,
    Callout,
    TemplateBox.configure({
      // Nur im echten Workspace anbieten (der DevHarness hat keinen Baustein-Speicher).
      onSaveAsTemplate: props.workspace ? (data) => emit('save-block-template', data) : null,
    }),
    TemplateField,
    NoteImage,
    FileHandler.configure({
      allowedMimeTypes: NOTE_IMAGE_MIME_TYPES,
      consumePasteEvent: true,
      onPaste: (_ed, files) => { void uploadImageFiles(files); },
      onDrop: (_ed, files, pos) => { void uploadImageFiles(files, { position: pos }); },
    }),
    HistoryFlash,
    NoteSearch,
    CleanupReviewAnchor.configure({
      onMount: (element) => { cleanupAnchorEl.value = element; },
      onDestroy: (element) => {
        if (cleanupAnchorEl.value === element) cleanupAnchorEl.value = null;
      },
    }),
  ],
  editorProps: {
    attributes: { class: 'pm-content', spellcheck: props.spellcheckEnabled ? 'true' : 'false' },
    handleKeyDown: (_view, event) => onEditorKeyDown(event),
    handlePaste: (_view, event) => handleEditorPaste(event),
    handleClick: (view, _pos, event) => handleEditorLinkClick(view, event),
  },
  onUpdate: ({ editor: ed }) => {
    // Dokument nur EINMAL pro Anschlag serialisieren und für beide Emits sowie
    // die Wortzählung wiederverwenden (statt getJSON×2 + getText×2).
    const json = ed.getJSON();
    const text = ed.getText();
    lastEmittedModelValue = json;
    updateWordCount(ed, text);
    emit('update:modelValue', json);
    emit('change', { json, text, words: words.value });
    refreshWikiLink();
    refreshSlash();
    emitNoteSearchState(ed);
  },
  onSelectionUpdate: () => {
    tableMenu.open = false;
    linkEditor.open = false;
    refreshBubble();
    refreshWikiLink();
    refreshSlash();
    nextTick(refreshTableHandle);
  },
  onTransaction: ({ editor: ed, transaction }) => {
    if (cleanupRestore.open && transaction.docChanged) {
      cleanupRestore.open = false;
      nextTick(() => hideCleanupReviewAnchor(ed));
    }
    if (!isHistoryTransaction(transaction)) {
      if (transaction.docChanged || transaction.selectionSet) dismissHistoryFlash(ed);
      return;
    }
    if (!transaction.docChanged) return;
    const range = historyChangedRange(transaction.before, transaction.doc);
    if (range) scheduleHistoryFlash(ed, range);
  },
  onCreate: ({ editor: ed }) => {
    updateWordCount(ed);
    nextTick(refreshTableHandle);
  },
});

onMounted(() => {
  if (props.autofocus) nextTick(() => titleEl.value?.focus());
  if (props.workspace) nextTick(() => bindFormattingToolbarScroll());
  window.addEventListener('resize', refreshBubble);
  nextTick(() => applySpellcheck(props.spellcheckEnabled));
  nextTick(() => {
    if (props.workspace && writingEl.value && typeof ResizeObserver !== 'undefined') {
      emptyHintResizeObserver = new ResizeObserver(scheduleEmptyHintPosition);
      emptyHintResizeObserver.observe(writingEl.value);
    }
    scheduleEmptyHintPosition();
  });
});

watch(() => props.spellcheckEnabled, (enabled) => applySpellcheck(enabled));
watch(() => props.readonly, (readonly) => editor.value?.setEditable(!readonly));

onBeforeUnmount(() => {
  editor.value?.destroy();
  toolbarScrollContainer?.removeEventListener('scroll', onEditorScroll);
  window.removeEventListener('resize', refreshBubble);
  if (toolbarScrollRestoreFrame) window.cancelAnimationFrame(toolbarScrollRestoreFrame);
  if (historyFlashTimer) window.clearTimeout(historyFlashTimer);
  if (imageUploadMessageTimer) window.clearTimeout(imageUploadMessageTimer);
  if (emptyHintPositionFrame) window.cancelAnimationFrame(emptyHintPositionFrame);
  emptyHintResizeObserver?.disconnect();
});

function scheduleHistoryFlash(ed, range) {
  nextTick(() => {
    if (ed.isDestroyed) return;
    showHistoryFlash(ed, range);
    if (historyFlashTimer) window.clearTimeout(historyFlashTimer);
    historyFlashTimer = window.setTimeout(() => {
      clearHistoryFlash(ed);
      historyFlashTimer = null;
    }, 720);
  });
}

function dismissHistoryFlash(ed) {
  if (!historyFlashTimer) return;
  window.clearTimeout(historyFlashTimer);
  historyFlashTimer = null;
  clearHistoryFlash(ed);
}

function bindFormattingToolbarScroll() {
  toolbarScrollContainer = surfaceEl.value?.closest('.note-workspace-editor__scroll') || null;
  toolbarScrollContainer?.addEventListener('scroll', onEditorScroll, { passive: true });
  onEditorScroll();
}

function applySpellcheck(enabled) {
  editor.value?.view?.dom?.setAttribute('spellcheck', enabled ? 'true' : 'false');
}

// Beim Scrollen wird der Guard leicht durchscheinend und offene Overlays werden
// an der neuen Textposition ausgerichtet. Am Seitenanfang bleibt die Fläche
// deckend, damit der Übergang zur Metazeile ruhig wirkt.
function onEditorScroll() {
  toolbarScrolled.value = Boolean(toolbarScrollContainer?.scrollTop > 2);
  if (slash.open) refreshSlash();
  if (bubble.show) refreshBubble();
  if (aiPrompt.open && aiPrompt.presentation === 'dialog') positionAIPrompt();
}

function restoreWorkspaceScroll(top) {
  const scrollElement = toolbarScrollContainer
    || surfaceEl.value?.closest('.note-workspace-editor__scroll');
  if (!scrollElement) return;
  const targetTop = Math.max(0, Number(top) || 0);
  scrollElement.scrollTop = targetTop;
  toolbarScrolled.value = targetTop > 2;
  if (toolbarScrollRestoreFrame) window.cancelAnimationFrame(toolbarScrollRestoreFrame);
  toolbarScrollRestoreFrame = window.requestAnimationFrame(() => {
    // Chromium kann die Auswahl beim Einblenden eines Overlays erst im
    // nächsten Frame nachführen. Ein zweites Setzen hält dabei die zuvor
    // gewählte Schreibposition stabil.
    scrollElement.scrollTop = targetTop;
    toolbarScrollRestoreFrame = null;
  });
}

// Externe modelValue-Änderung (z. B. Reset) übernehmen, ohne Tipp-Feedback-Loop.
watch(() => props.modelValue, (next) => {
  const ed = editor.value;
  if (!ed) return;
  // Häufigster Fall: die Änderung stammt vom Editor selbst (onUpdate → emit →
  // Parent-Body → zurück als prop). Der Parent hält den Body in einem ref, daher
  // kommt er als reaktiver Proxy zurück – `toRaw` vergleicht die zugrunde
  // liegende Objektreferenz und bricht ab, BEVOR das ganze Dokument zweimal
  // serialisiert wird (was zusätzlich Deep-Proxying auslösen würde).
  if (toRaw(next) === lastEmittedModelValue) return;
  // Nur bei echten externen Änderungen (Notizwechsel, KI-Ergebnis, Entwurfs-
  // wiederherstellung) den teuren Strukturvergleich durchführen.
  const current = JSON.stringify(ed.getJSON());
  if (JSON.stringify(next || '') === current) return;
  // Ein verzögertes KI-Ergebnis darf niemals in eine inzwischen ausgewählte
  // andere Notiz geschrieben werden.
  overlays.closeAll();
  ed.commands.setContent(next || '', { emitUpdate: false });
  resetSelectionAfterExternalContent(ed);
  updateWordCount(ed);
  emitNoteSearchState(ed);
  nextTick(refreshTableHandle);
});

// Beim Notizwechsel (externe modelValue-Änderung) sauber aufräumen. Zwei
// Chromium/ProseMirror-Fallen verursachen sonst die gemeldeten Schreibmarken-
// Probleme:
//   1. setContent bildet in TipTap v3 die bisherige Auswahl auf das NEUE Dokument
//      ab → die Schreibmarke landet an einer willkürlichen Position.
//   2. setTextSelection schreibt die DOM-Auswahl NUR, wenn der Editor gerade
//      fokussiert ist. Beim Wechsel bleibt sonst eine veraltete DOM-Auswahl der
//      vorigen Notiz stehen. Die zugehörige native Schreibmarke wird gezeichnet
//      und beim nächsten Repaint nicht sauber gelöscht → „Geister"-Schreibmarken
//      und Marken, die mitten im Leerraum stehen.
// Deshalb: PM-Auswahl deterministisch an den Anfang, veraltete DOM-Auswahl
// verwerfen und den Editor defokussieren. Explizite Fokus-Pfade (Verwaltungs-
// raster/neue Notiz rufen focusBody nach nextTick) setzen den Fokus danach
// gezielt neu.
function resetSelectionAfterExternalContent(ed) {
  ed.commands.setTextSelection(0);
  if (typeof window !== 'undefined') {
    const domSel = window.getSelection?.();
    if (domSel?.rangeCount && ed.view?.dom?.contains(domSel.anchorNode)) {
      domSel.removeAllRanges();
    }
  }
  ed.commands.blur();
}

function isPristineEmptyDocument(ed) {
  const doc = ed?.state?.doc;
  const firstBlock = doc?.firstChild;
  return Boolean(
    doc?.childCount === 1
    && firstBlock?.type?.name === 'paragraph'
    && firstBlock.content.size === 0
  );
}

function updateWordCount(ed, text) {
  // TipTap betrachtet auch mehrere leere Absätze als `isEmpty`. Der visuelle
  // Schreibhilfe-Zustand gilt jedoch nur für das unberührte Startdokument.
  editorEmpty.value = isPristineEmptyDocument(ed);
  if (editorEmpty.value) scheduleEmptyHintPosition();
  else emptyHintPositioned.value = false;
  // Text wird vom Aufrufer durchgereicht, wenn er ihn ohnehin schon ermittelt hat
  // (onUpdate) – sonst hier einmal holen.
  words.value = countWords(text ?? ed?.getText());
  emit('word-count', words.value);
}

function scheduleEmptyHintPosition() {
  if (!props.workspace || !editorEmpty.value) return;
  nextTick(() => {
    if (emptyHintPositionFrame) window.cancelAnimationFrame(emptyHintPositionFrame);
    emptyHintPositionFrame = window.requestAnimationFrame(() => {
      emptyHintPositionFrame = null;
      const writing = writingEl.value;
      const firstParagraph = writing?.querySelector('.pm-content > p:first-child');
      if (!writing || !firstParagraph || !editorEmpty.value) return;

      const writingRect = writing.getBoundingClientRect();
      const paragraphRect = firstParagraph.getBoundingClientRect();
      emptyHintStyle.value = {
        top: `${paragraphRect.top - writingRect.top}px`,
        left: `${paragraphRect.left - writingRect.left}px`,
      };
      emptyHintPositioned.value = true;
    });
  });
}

function countWords(text) {
  const t = (text || '').trim();
  return t ? t.split(/\s+/).length : 0;
}

function focusBody(position) {
  const ed = editor.value;
  if (!ed?.isEditable) return false;
  if (position === 'start' || position === 'end') {
    ed.chain().focus(position).run();
    return true;
  }
  ed.chain().focus().run();
  return true;
}

function refocusEditorFromWhitespace(event) {
  const ed = editor.value;
  const surface = surfaceEl.value;
  const target = event.target;
  if (!ed?.isEditable || !surface || event.button !== 0 || !(target instanceof Element)) return;

  // Text und eingebettete Elemente behalten ihr natives Auswahl-/Klickverhalten.
  // Nur die ProseMirror-Grundfläche selbst sowie der umgebende Editorleerraum
  // werden zur großen, komfortablen Fokuszone.
  if (target.closest('.pm-float, button, input, select, textarea, a')) return;
  const content = surface.querySelector('.pm-content');
  if (!content || (content.contains(target) && target !== content)) return;

  event.preventDefault();
  const { selection } = ed.state;
  const chain = ed.chain();

  // Ein Klick auf die große Editorfläche ist ein neutraler Refokus: Eine
  // bestehende Textauswahl wird am aktiven Ende eingeklappt, eine vorhandene
  // Schreibmarke bleibt dagegen unverändert. Weder Auswahl noch Scrollposition
  // springen dadurch pauschal ans Dokumentende.
  if (selection instanceof TextSelection && !selection.empty) {
    chain.setTextSelection(selection.head);
  }
  chain.focus(undefined, { scrollIntoView: false }).run();
}

function focusTitle() {
  titleEl.value?.focus();
}

function emitNoteSearchState(ed = editor.value) {
  const state = getNoteSearchState(ed);
  emit('note-search-state', {
    query: state.query,
    count: state.ranges.length,
    activeIndex: state.activeIndex,
  });
  return state;
}

function scrollToDocumentPosition(position, { focus = false, behavior = 'smooth' } = {}) {
  const ed = editor.value;
  if (!ed || ed.isDestroyed) return false;
  const maxPosition = Math.max(0, ed.state.doc.content.size);
  const targetPosition = Math.min(maxPosition, Math.max(0, Number(position) || 0));
  const scrollElement = toolbarScrollContainer
    || surfaceEl.value?.closest('.note-workspace-editor__scroll');
  if (!scrollElement) return false;

  if (focus) {
    ed.chain().focus().setTextSelection(Math.min(maxPosition, targetPosition + 1)).run();
  }
  window.requestAnimationFrame(() => {
    if (ed.isDestroyed) return;
    const nodeDom = ed.view.nodeDOM(targetPosition);
    const targetRect = nodeDom instanceof Element
      ? nodeDom.getBoundingClientRect()
      : ed.view.coordsAtPos(Math.min(maxPosition, targetPosition + 1));
    const scrollRect = scrollElement.getBoundingClientRect();
    const toolbarOffset = props.workspace ? 62 : 18;
    scrollElement.scrollTo({
      top: Math.max(0, scrollElement.scrollTop + targetRect.top - scrollRect.top - toolbarOffset),
      behavior,
    });
  });
  return true;
}

function searchInNote(query, activeIndex = 0) {
  const state = setNoteSearch(editor.value, query, activeIndex);
  emitNoteSearchState();
  const activeRange = state.ranges[state.activeIndex];
  if (activeRange) scrollToDocumentPosition(activeRange.from, { behavior: 'smooth' });
  return { count: state.ranges.length, activeIndex: state.activeIndex };
}

function selectNoteSearchResult(activeIndex) {
  const current = getNoteSearchState(editor.value);
  return searchInNote(current.query, activeIndex);
}

// Ersetzt den aktuell hervorgehobenen Treffer und rückt automatisch auf den
// nächsten vor (der Index bleibt stehen, der ersetzte Treffer fällt weg).
function replaceActiveNoteSearch(replaceText) {
  const ed = editor.value;
  if (!ed || ed.isDestroyed) return { count: 0, activeIndex: -1 };
  const { ranges, activeIndex, query } = getNoteSearchState(ed);
  const range = ranges[activeIndex];
  if (!range) return { count: ranges.length, activeIndex };
  ed.view.dispatch(ed.state.tr.insertText(String(replaceText ?? ''), range.from, range.to));
  return searchInNote(query, activeIndex);
}

// Ersetzt alle Treffer in EINER Transaktion (ein Undo-Schritt). Von hinten nach
// vorn, damit die vorderen Positionen gültig bleiben.
function replaceAllNoteSearch(replaceText) {
  const ed = editor.value;
  if (!ed || ed.isDestroyed) return { count: 0, activeIndex: -1 };
  const { ranges, query } = getNoteSearchState(ed);
  if (!ranges.length) return { count: 0, activeIndex: -1 };
  const text = String(replaceText ?? '');
  const tr = ed.state.tr;
  for (let i = ranges.length - 1; i >= 0; i -= 1) {
    tr.insertText(text, ranges[i].from, ranges[i].to);
  }
  ed.view.dispatch(tr);
  return searchInNote(query, 0);
}

function clearNoteSearch() {
  setNoteSearch(editor.value, '', -1);
  emitNoteSearchState();
}

defineExpose({
  clearNoteSearch,
  focusTitle,
  focusBody,
  openShortcuts,
  replaceActiveNoteSearch,
  replaceAllNoteSearch,
  restoreWorkspaceScroll,
  scrollToDocumentPosition,
  searchInNote,
  selectNoteSearchResult,
});

function onTitleInput(e) {
  emit('update:title', e.target.value);
}

function toolbarActive(name, attrs = undefined) {
  return attrs ? editor.value?.isActive(name, attrs) : editor.value?.isActive(name);
}

function runToolbar(action) {
  const ed = editor.value;
  if (!ed) return;
  tableMenu.open = false;
  closeLinkEditor();
  const chain = ed.chain().focus();
  const commands = {
    h2: () => chain.toggleHeading({ level: 2 }),
    h3: () => chain.toggleHeading({ level: 3 }),
    h4: () => chain.toggleHeading({ level: 4 }),
    paragraph: () => chain.setParagraph(),
    bold: () => chain.toggleBold(),
    italic: () => chain.toggleItalic(),
    underline: () => chain.toggleUnderline(),
    code: () => chain.toggleCode(),
    bulletList: () => chain.toggleBulletList(),
    orderedList: () => chain.toggleOrderedList(),
    taskList: () => chain.toggleTaskList(),
    blockquote: () => chain.toggleBlockquote(),
    codeBlock: () => chain.toggleCodeBlock(),
    horizontalRule: () => chain.setHorizontalRule(),
  };
  commands[action]?.().run();
}

/* ── Feature-Controller teilen die bestehende Editor-Instanz ─────────────── */

const links = useNoteLinks({ editor, surfaceEl, props, overlays, clampMenuLeft });
const tables = useNoteTables({ editor, surfaceEl, props, overlays, clampMenuLeft });
const references = useNoteReferences({ editor, surfaceEl, props, overlays, clampMenuLeft, getTargets: linkTargetItems });
const { linkEditor, openLinkEditor, closeLinkEditor, handleEditorPaste, handleEditorLinkClick } = links;
const { tableMenu, openTableMenu, closeTableMenu, refreshTableHandle, trackTableHandle, clearHoveredTable, handleTableKeydown } = tables;
const { picker, openPicker, refreshWikiLink, handlePickerKeydown } = references;
const stream = inject(NOTE_AI_STREAM, undefined);
const writing = useNoteWriting({ editor, surfaceEl, props, overlays, clampMenuLeft, stream, onCheckpoint: (reason) => emit('history-checkpoint', reason) });
const cleaning = useNoteCleanup({ editor, props, overlays, stream, onCheckpoint: (reason) => emit('history-checkpoint', reason) });
const { aiPrompt, aiOptionsOpen, openAIPrompt, positionAIPrompt } = writing;
const { cleanup, cleanupRestore, cleanupAnchorEl, startCleanup, discardCleanup } = cleaning;
const rootEl = ref(null);
const toolbar = useNoteToolbar({
  editor, rootEl, props, runToolbar, closeLinkEditor,
  closeTableMenu,
  beforeOpen: () => overlays.open('toolbar'),
  onOutsidePointer: (event) => {
    if (!event.target.closest?.('.note-editor__toolbar-ai')) aiOptionsOpen.value = false;
  },
  documentsAvailable: () => docPickerItems().length > 0,
  targetsAvailable: () => linkTargetItems().length > 0,
  imageUploading: () => imageUploadCount.value > 0,
  onInsert: (action) => {
    const actions = { table: openTableMenu, link: openLinkEditor, image: openImagePicker, document: openDocumentChipPicker, target: openLinkTargetPicker };
    actions[action]?.();
  },
});
const { openMenu, isTextHighlightActive, applyTextHighlight, removeTextHighlight } = toolbar;
overlays.register('toolbar', () => { openMenu.value = null; });
overlays.register('slash', () => { slash.open = false; });
overlays.register('bubble', () => { bubble.show = false; });
// Auch Notizen mit identischem Inhalt dürfen keine alten Menüzustände behalten.
watch(() => props.noteId, () => overlays.closeAll());

function setImageUploadMessage(message, { error = false } = {}) {
  imageUploadMessage.value = String(message || '');
  imageUploadError.value = Boolean(error);
  if (imageUploadMessageTimer) window.clearTimeout(imageUploadMessageTimer);
  imageUploadMessageTimer = window.setTimeout(() => {
    imageUploadMessage.value = '';
    imageUploadError.value = false;
    imageUploadMessageTimer = null;
  }, error ? 5200 : 2400);
}

function openImagePicker() {
  if (!props.noteId || props.readonly || imageUploadCount.value > 0) return;
  slash.open = false;
  picker.open = false;
  tableMenu.open = false;
  closeLinkEditor();
  if (imageInputEl.value) {
    imageInputEl.value.value = '';
    imageInputEl.value.click();
  }
}

function onImageInput(event) {
  const files = Array.from(event.target?.files || []);
  if (event.target) event.target.value = '';
  void uploadImageFiles(files);
}

async function uploadImageFiles(inputFiles, { position = null } = {}) {
  const ed = editor.value;
  const noteId = props.noteId;
  if (!ed?.isEditable || !noteId) {
    setImageUploadMessage('Bilder können erst in einer gespeicherten Notiz eingefügt werden.', { error: true });
    return;
  }

  const incoming = Array.from(inputFiles || []);
  const supported = incoming.filter((file) => NOTE_IMAGE_MIME_TYPES.includes(file.type));
  if (!supported.length) {
    const message = 'Bitte ein JPEG-, PNG- oder WebP-Bild auswählen.';
    setImageUploadMessage(message, { error: true });
    emit('image-upload-error', message);
    return;
  }
  const files = supported.slice(0, NOTE_IMAGE_UPLOAD_LIMIT);
  if (incoming.length > NOTE_IMAGE_UPLOAD_LIMIT) {
    setImageUploadMessage(`Pro Vorgang können höchstens ${NOTE_IMAGE_UPLOAD_LIMIT} Bilder eingefügt werden.`, { error: true });
  }

  imageUploadCount.value += files.length;
  imageUploadMessage.value = '';
  imageUploadError.value = false;
  const results = await Promise.allSettled(files.map((file) => uploadNoteImage(noteId, file)));
  imageUploadCount.value = Math.max(0, imageUploadCount.value - files.length);

  const images = results
    .filter((result) => result.status === 'fulfilled')
    .map((result) => result.value);
  const failures = results.filter((result) => result.status === 'rejected');

  // A slow upload must never land in a note selected in the meantime.
  if (props.noteId !== noteId || editor.value !== ed || ed.isDestroyed) return;

  if (images.length) {
    const content = images.map((image) => ({
      type: 'image',
      attrs: {
        src: image.src,
        imageId: image.id,
        noteId: image.note_id,
        title: image.filename,
        alt: image.filename,
        caption: '',
        width: image.width,
        height: image.height,
        displayWidth: 100,
      },
    }));
    content.push({ type: 'paragraph' });
    const chain = ed.chain().focus();
    if (Number.isInteger(position)) {
      chain.insertContentAt(Math.max(0, Math.min(position, ed.state.doc.content.size)), content, {
        updateSelection: true,
      });
    } else {
      chain.insertContent(content);
    }
    chain.scrollIntoView().run();
  }

  if (failures.length) {
    const first = failures[0].reason?.message || 'Mindestens ein Bild konnte nicht eingefügt werden.';
    const message = failures.length === 1
      ? first
      : `${failures.length} Bilder konnten nicht eingefügt werden. ${first}`;
    setImageUploadMessage(message, { error: true });
    emit('image-upload-error', message);
  } else if (images.length > 1) {
    setImageUploadMessage(`${images.length} Bilder wurden eingefügt.`);
  }
}

/* ── Status-Anzeige ──────────────────────────────────────────────────────── */
const saveLabel = computed(() => (
  { saving: 'Speichert …', saved: 'Gespeichert', idle: 'Bereit' }[props.status] || 'Bereit'
));

/* ── Bubble-Menü (Auswahl-Formatierung) ─────────────────────────────────────── */
const bubble = reactive({ show: false, style: {} });
// Textmarker in der Auswahl-Bubble: klappt eine kompakte Farbreihe auf und nutzt
// dieselbe Highlight-Logik wie zuvor die obere Leiste (setNoteHighlight …).
const bubbleHighlight = reactive({ open: false });
function toggleBubbleHighlight() {
  bubbleHighlight.open = !bubbleHighlight.open;
}
function applyBubbleHighlight(color) {
  applyTextHighlight(color);
  bubbleHighlight.open = false;
  refreshBubble();
}
function removeBubbleHighlight() {
  removeTextHighlight();
  bubbleHighlight.open = false;
  refreshBubble();
}
const BUBBLE_VIEWPORT_MARGIN = 8;
const BUBBLE_BUTTON_WIDTH = 32;
const BUBBLE_AI_BUTTON_WIDTH = 36;
const BUBBLE_GAP = 2;
const BUBBLE_SHELL_WIDTH = 10;
const BUBBLE_ESTIMATED_HEIGHT = 40;
const BUBBLE_SELECTION_GAP = 8;
let bubblePositionRevision = 0;

const bubbleButtons = computed(() => {
  const ed = editor.value;
  if (!ed) return [];
  const mk = (key, label, icon, isActive, run) => ({
    key, label, icon,
    active: () => isActive(ed),
    run: () => { run(ed.chain().focus()).run(); refreshBubble(); },
  });
  return [
    mk('bold', 'Fett', 'mdi-format-bold', e => e.isActive('bold'), c => c.toggleBold()),
    mk('italic', 'Kursiv', 'mdi-format-italic', e => e.isActive('italic'), c => c.toggleItalic()),
    mk('underline', 'Unterstrichen', 'mdi-format-underline', e => e.isActive('underline'), c => c.toggleUnderline()),
    mk('strike', 'Durchgestrichen', 'mdi-format-strikethrough-variant', e => e.isActive('strike'), c => c.toggleStrike()),
    mk('code', 'Code', 'mdi-code-tags', e => e.isActive('code'), c => c.toggleCode()),
    {
      key: 'link',
      label: 'Hyperlink',
      icon: 'mdi-link-variant',
      active: () => ed.isActive('link'),
      run: () => openLinkEditor(),
    },
    {
      key: 'highlight',
      label: 'Textmarker',
      icon: 'mdi-format-color-highlight',
      active: () => toolbarActive('highlight') || bubbleHighlight.open,
      run: () => toggleBubbleHighlight(),
    },
    ...(props.aiAvailable ? [{
      key: 'ai-selection',
      label: 'Umschreiben',
      icon: 'mdi-auto-fix',
      ai: true,
      active: () => false,
      run: () => openAIPrompt(),
    }, {
      key: 'ai-cleanup',
      label: 'Aufräumen (sinnwahrend)',
      icon: 'mdi-broom',
      ai: true,
      active: () => false,
      run: () => startCleanup(),
    }] : []),
  ];
});

function refreshBubble() {
  const revision = ++bubblePositionRevision;
  // Bei jeder Auswahländerung die Farbreihe wieder einklappen.
  bubbleHighlight.open = false;
  const ed = editor.value;
  const surface = surfaceEl.value;
  if (!ed || !surface) { bubble.show = false; return; }
  const { state, view } = ed;
  const { from, to, empty } = state.selection;
  const isText = state.selection instanceof TextSelection;
  if (empty || !isText || !ed.isEditable || slash.open || picker.open || tableMenu.open || linkEditor.open) {
    bubble.show = false;
    return;
  }

  const rect = posToDOMRect(view, from, to);
  const scrollRect = toolbarScrollContainer?.getBoundingClientRect();
  const toolbarRect = rootEl.value
    ?.querySelector('.note-editor__toolbar-guard')
    ?.getBoundingClientRect();
  const viewportTop = Math.max(
    BUBBLE_VIEWPORT_MARGIN,
    scrollRect?.top ?? BUBBLE_VIEWPORT_MARGIN,
    toolbarRect?.bottom ?? BUBBLE_VIEWPORT_MARGIN,
  );
  const viewportBottom = Math.min(
    window.innerHeight - BUBBLE_VIEWPORT_MARGIN,
    scrollRect?.bottom ?? window.innerHeight - BUBBLE_VIEWPORT_MARGIN,
  );
  const estimatedWidth = bubbleButtons.value.reduce(
    (width, button) => width + (button.ai ? BUBBLE_AI_BUTTON_WIDTH + 3 : BUBBLE_BUTTON_WIDTH),
    BUBBLE_SHELL_WIDTH + Math.max(0, bubbleButtons.value.length - 1) * BUBBLE_GAP,
  );
  const clampCenterToViewport = (width) => {
    const availableWidth = Math.max(0, window.innerWidth - BUBBLE_VIEWPORT_MARGIN * 2);
    const halfWidth = Math.min(width, availableWidth) / 2;
    const minCenter = BUBBLE_VIEWPORT_MARGIN + halfWidth;
    const maxCenter = Math.max(
      minCenter,
      window.innerWidth - BUBBLE_VIEWPORT_MARGIN - halfWidth,
    );
    return Math.max(
      minCenter,
      Math.min(rect.left + rect.width / 2, maxCenter),
    );
  };
  const positionBubble = (height) => placeSelectionBubble({
    selectionRect: rect,
    viewportTop,
    viewportBottom,
    bubbleHeight: height,
    gap: BUBBLE_SELECTION_GAP,
  });
  const estimatedPosition = positionBubble(BUBBLE_ESTIMATED_HEIGHT);
  if (!estimatedPosition) {
    bubble.show = false;
    return;
  }
  bubble.style = {
    left: `${clampCenterToViewport(estimatedWidth)}px`,
    top: `${estimatedPosition.top}px`,
    transform: 'translateX(-50%)',
  };
  bubble.show = true;
  nextTick(() => {
    const measuredWidth = bubbleEl.value?.offsetWidth;
    const measuredHeight = bubbleEl.value?.offsetHeight;
    if (revision !== bubblePositionRevision || !bubble.show || !measuredWidth || !measuredHeight) return;
    const measuredPosition = positionBubble(measuredHeight);
    if (!measuredPosition) {
      bubble.show = false;
      return;
    }
    bubble.style = {
      ...bubble.style,
      left: `${clampCenterToViewport(measuredWidth)}px`,
      top: `${measuredPosition.top}px`,
    };
  });
}

/* ── Slash-Menü ──────────────────────────────────────────────────────────── */
const SLASH_COMMANDS = [
  // Vorlagen — gefärbte Feld-Blöcke mit Platzhaltern.
  ...NOTE_TEMPLATE_PRESETS.map((preset) => ({
    key: `template-${preset.key}`,
    group: 'templates',
    chip: preset.chip || '▤',
    label: preset.label,
    desc: preset.desc,
    terms: preset.terms || [],
    action: (chain) => chain.insertTemplateBox(preset),
  })),
  // PaperMind-eigene Bausteine.
  { key: 'beleg', group: 'papermind', chip: '▢', label: 'Beleg verknüpfen', desc: 'Dokument-Chip einfügen', terms: ['beleg', 'dokument', 'chip', 'verknüpfen'], kind: 'pick-doc-chip' },
  { key: 'zitat', group: 'papermind', chip: '❝', label: 'Beleg-Zitat', desc: 'OCR-Passage übernehmen', terms: ['zitat', 'beleg', 'ocr', 'markierung'], kind: 'pick-doc-quote' },
  { key: 'ki-schreiben', group: 'papermind', chip: '✦', label: 'Mit KI schreiben', desc: 'Text generieren und einfügen', terms: ['ki', 'ai', 'prompt', 'schreiben', 'text', 'generieren'], kind: 'generate-ai' },
  { key: 'ki-aufraeumen', group: 'papermind', chip: '⌁', label: 'Aufräumen (sinnwahrend)', desc: 'Fragmente zu lesbaren Sätzen glätten', terms: ['aufräumen', 'aufraeumen', 'glätten', 'glaetten', 'ausformulieren', 'sätze', 'lesbar', 'sinnwahrend', 'cleanup', 'ki', 'ai'], kind: 'cleanup' },
  { key: 'verweis', group: 'papermind', chip: '[[', label: 'Verweis', desc: 'Notiz / Beleg / Person', terms: ['verweis', 'link', 'wiki', 'verknüpfung'], kind: 'pick-target' },
  ...NOTE_CALLOUT_OPTIONS.map((option) => ({
    key: `callout-${option.value}`,
    group: 'callouts',
    chip: option.glyph,
    label: option.label,
    desc: option.description,
    terms: [...option.terms, 'callout', 'hinweisbox'],
    action: (chain) => chain.insertCallout(option.value),
  })),
  { key: 'h2', group: 'headings', chip: 'H2', label: 'Überschrift 2', desc: 'Unterabschnitt', terms: ['überschrift', 'h2'], action: c => c.toggleHeading({ level: 2 }) },
  { key: 'h3', group: 'headings', chip: 'H3', label: 'Überschrift 3', desc: 'Kleiner Abschnitt', terms: ['überschrift', 'h3'], action: c => c.toggleHeading({ level: 3 }) },
  { key: 'h4', group: 'headings', chip: 'H4', label: 'Überschrift 4', desc: 'Feiner Unterabschnitt', terms: ['überschrift', 'h4'], action: c => c.toggleHeading({ level: 4 }) },
  { key: 'link', group: 'inline', chip: '↗', label: 'Hyperlink', desc: 'Webseite oder E-Mail verlinken', terms: ['link', 'hyperlink', 'url', 'webseite', 'website', 'e-mail', 'email'], kind: 'link-editor' },
  { key: 'ul', group: 'blocks', chip: '•', label: 'Aufzählung', desc: 'Ungeordnete Liste', terms: ['liste', 'aufzählung', 'bullet'], action: c => c.toggleBulletList() },
  { key: 'ol', group: 'blocks', chip: '1.', label: 'Nummerierte Liste', desc: 'Geordnete Liste', terms: ['liste', 'nummer', 'ordered'], action: c => c.toggleOrderedList() },
  { key: 'task', group: 'blocks', chip: '☑', label: 'Aufgabenliste', desc: 'Checkboxen', terms: ['aufgabe', 'todo', 'task', 'checkbox'], action: c => c.toggleTaskList() },
  { key: 'table', group: 'blocks', chip: '▦', label: 'Tabelle', desc: 'Zeilen und Spalten', terms: ['tabelle', 'table', 'raster', 'zeile', 'spalte'], kind: 'table-menu' },
  { key: 'image', group: 'blocks', chip: '▧', label: 'Bild', desc: 'Foto oder Grafik einfügen', terms: ['bild', 'foto', 'grafik', 'image', 'upload'], kind: 'image-upload' },
  { key: 'quote', group: 'blocks', chip: '❝', label: 'Zitat', desc: 'Zitatblock', terms: ['zitat', 'quote'], action: c => c.toggleBlockquote() },
  { key: 'code', group: 'blocks', chip: '</>', label: 'Code-Block', desc: 'Monospace', terms: ['code', 'block'], action: c => c.toggleCodeBlock() },
  { key: 'hr', group: 'blocks', chip: '―', label: 'Trennlinie', desc: 'Horizontale Linie', terms: ['trennlinie', 'linie', 'rule'], action: c => c.setHorizontalRule() },
];

const SLASH_GROUPS = [
  { key: 'templates', label: 'Schnellblöcke' },
  { key: 'callouts', label: 'Hinweisblöcke' },
  { key: 'headings', label: 'Überschriften' },
  { key: 'inline', label: 'Text & Links' },
  { key: 'blocks', label: 'Listen & Blöcke' },
  { key: 'papermind', label: 'PaperMind' },
];

const slashCommandUsage = ref(loadSlashCommandUsage());

const slash = reactive({
  open: false,
  query: '',
  from: null,
  index: 0,
  codeOnly: false,
  style: {},
  selectionStyle: {},
  selectionVisible: false,
});

// „Real-Modus": echte Datenquelle vorhanden (Workspace) → Mock-only-Befehle
// ausblenden. Die echte Textgenerierung bleibt in beiden Varianten verfügbar.
const realMode = computed(() => Array.isArray(props.documentItems));

// Benutzereigene Bausteine als Slash-Befehle (Gruppe „Bausteine", neben dem
// mitgelieferten Preset). Einfügen läuft über dasselbe insertTemplateBox.
const blockTemplateCommands = computed(() =>
  (props.blockTemplates || []).map((tpl) => {
    const fields = Array.isArray(tpl.fields) ? tpl.fields : [];
    const labels = fields.map((f) => f.label).filter(Boolean).join(' · ');
    return {
      key: `blocktpl-${tpl.id}`,
      group: 'templates',
      chip: '▤',
      label: tpl.name || tpl.title || 'Schnellblock',
      desc: labels || 'Eigener Baustein',
      terms: [tpl.name, tpl.title, 'schnellblock', 'baustein', 'vorlage']
        .filter(Boolean)
        .map((t) => String(t).toLowerCase()),
      action: (chain) => chain.insertTemplateBox({
        title: tpl.title || '',
        color: tpl.color || 'teal',
        fields,
      }),
    };
  })
);

const availableSlashCommands = computed(() =>
  [...SLASH_COMMANDS, ...blockTemplateCommands.value].filter((command) => {
    if (realMode.value && command.kind === 'pick-doc-quote') return false;
    if (!props.aiAvailable && (command.kind === 'generate-ai' || command.kind === 'cleanup')) return false;
    if (!props.noteId && command.kind === 'image-upload') return false;
    return true;
  })
);

const slashResults = computed(() => {
  const base = slash.codeOnly
    ? availableSlashCommands.value.filter((command) => command.kind === 'generate-ai')
    : availableSlashCommands.value;
  const q = slash.query.trim().toLowerCase();
  if (!q) return base;
  return base.filter(c =>
    c.label.toLowerCase().includes(q) || c.terms.some(t => t.includes(q))
  );
});

const frequentSlashCommands = computed(() => (
  mostUsedSlashCommands(availableSlashCommands.value, slashCommandUsage.value)
));

const slashGroups = computed(() => {
  let flatIndex = 0;
  const matchingCommandKeys = new Set(slashResults.value.map((command) => command.key));
  const indexCommands = (commands) => (
    commands.map((command) => ({ command, index: flatIndex++ }))
  );
  return [
    {
      key: 'frequent',
      label: 'Häufig benutzt',
      items: indexCommands(
        frequentSlashCommands.value.filter((command) => matchingCommandKeys.has(command.key)),
      ),
    },
    ...SLASH_GROUPS.map((group) => ({
      ...group,
      items: indexCommands(
        slashResults.value.filter((command) => command.group === group.key),
      ),
    })),
  ].filter((group) => group.items.length);
});

// Die Tastaturauswahl muss exakt derselben, gruppierten Reihenfolge folgen wie
// die sichtbaren Einträge. SLASH_COMMANDS selbst ist bewusst unabhängig von
// der Präsentationsreihenfolge organisiert.
const slashMenuEntries = computed(() =>
  slashGroups.value.flatMap((group) => group.items)
);

// Menübreite (vgl. .pm-slash width) + Rand. Hält Slash-/Picker-Menü innerhalb
// der Schreibfläche, damit es am rechten Rand nicht abgeschnitten wird.
const MENU_WIDTH = 268;
const MENU_MARGIN = 8;
const MENU_GAP = 4;
const MENU_MAX_HEIGHT = 420;
const MENU_MIN_OPEN_HEIGHT = 180;
const MENU_VIEWPORT_MARGIN = 12;
function clampMenuLeft(rawLeft, boxWidth, menuWidth = MENU_WIDTH) {
  return Math.max(MENU_MARGIN, Math.min(rawLeft, boxWidth - menuWidth - MENU_MARGIN));
}

function clampViewportMenuLeft(rawLeft, surfaceRect, menuWidth = MENU_WIDTH) {
  const minLeft = Math.max(MENU_MARGIN, surfaceRect.left + MENU_MARGIN);
  const visibleRight = Math.min(window.innerWidth - MENU_MARGIN, surfaceRect.right - MENU_MARGIN);
  const maxLeft = Math.max(minLeft, visibleRight - menuWidth);
  return Math.max(minLeft, Math.min(rawLeft, maxLeft));
}

function slashMenuPlacement(rect, surfaceRect) {
  const scrollRect = toolbarScrollContainer?.getBoundingClientRect();
  const visibleTop = Math.max(0, scrollRect?.top ?? 0) + MENU_VIEWPORT_MARGIN;
  const visibleBottom = Math.min(window.innerHeight, scrollRect?.bottom ?? window.innerHeight)
    - MENU_VIEWPORT_MARGIN;
  const spaceBelow = Math.max(0, visibleBottom - rect.bottom - MENU_GAP);
  const spaceAbove = Math.max(0, rect.top - visibleTop - MENU_GAP);
  const opensAbove = spaceBelow < MENU_MIN_OPEN_HEIGHT && spaceAbove > spaceBelow;
  const maxHeight = Math.min(MENU_MAX_HEIGHT, opensAbove ? spaceAbove : spaceBelow);

  return {
    left: `${clampViewportMenuLeft(rect.left, surfaceRect)}px`,
    top: opensAbove ? 'auto' : `${rect.bottom + MENU_GAP}px`,
    bottom: opensAbove ? `${window.innerHeight - rect.top + MENU_GAP}px` : 'auto',
    maxHeight: `${Math.floor(maxHeight)}px`,
    transformOrigin: opensAbove ? '18px calc(100% + 5px)' : '18px -5px',
  };
}

function refreshSlash() {
  const ed = editor.value;
  const surface = surfaceEl.value;
  if (!ed || !surface) { slash.open = false; return; }
  const { state, view } = ed;
  const { $from, empty } = state.selection;
  if (!empty) { slash.open = false; return; }

  // Im Codeblock ist ausschließlich „Mit KI schreiben“ verfügbar. Andere
  // Blockbefehle könnten die umgebende Codestruktur ungültig machen.
  if (!$from.parent.isTextblock) { slash.open = false; return; }
  slash.codeOnly = $from.parent.type.name === 'codeBlock';

  const before = $from.parent.textBetween(0, $from.parentOffset, '￼', '￼');
  const match = /(?:^|\s)\/([\p{L}0-9]*)$/u.exec(before);
  if (!match) { slash.open = false; return; }

  const slashLen = match[1].length + 1;
  slash.from = state.selection.from - slashLen;
  slash.query = match[1];
  const opening = !slash.open;
  const scrollTopBeforeOpen = opening && toolbarScrollContainer
    ? toolbarScrollContainer.scrollTop
    : null;
  if (opening) {
    slash.index = 0;
    slash.selectionVisible = false;
  }
  slash.open = true;

  const rect = posToDOMRect(view, state.selection.from, state.selection.from);
  const box = surface.getBoundingClientRect();
  slash.style = slashMenuPlacement(rect, box);
  if (scrollTopBeforeOpen != null) {
    nextTick(() => restoreWorkspaceScroll(scrollTopBeforeOpen));
  }
  nextTick(updateSlashSelection);
}

function runSlash(cmd) {
  const ed = editor.value;
  if (!ed || slash.from == null) return;
  const to = ed.state.selection.from;
  const range = { from: slash.from, to };
  slash.open = false;
  recordSlashCommandUsage(cmd.key);

  const kind = cmd.kind || 'block';
  // Text entfernen und Block in EINER Transaktion ausführen. Zwischen zwei
  // separaten `run()`-Aufrufen kann das Workspace-v-model den Editorinhalt
  // spiegeln und dabei die Auswahl zurücksetzen; der zweite Befehl würde dann
  // nicht mehr an der Slash-Position ausgeführt.
  if (kind === 'block') {
    cmd.action(ed.chain().focus().deleteRange(range)).run();
    return;
  }

  // Picker und Dialoge brauchen den bereits bereinigten Editor als Ausgangs-
  // zustand, werden aber erst nach der Transaktion geöffnet.
  ed.chain().focus().deleteRange(range).run();
  if (kind === 'table-menu') { openTableMenu(ed.isActive('table') ? 'edit' : 'insert'); return; }
  if (kind === 'image-upload') { openImagePicker(); return; }
  if (kind === 'link-editor') { openLinkEditor(); return; }
  if (kind === 'generate-ai') { openAIPrompt(); return; }
  if (kind === 'cleanup') { startCleanup(); return; }
  if (kind === 'pick-doc-chip') {
    openDocumentChipPicker();
    return;
  }
  if (kind === 'pick-doc-quote') {
    openPicker('document', docPickerItems(), (item) => {
      const d = item._doc;
      ed.chain().focus().insertOcrQuote({ text: d.quote, docId: d.id, docTitle: d.title, page: d.quotePage }).run();
    });
    return;
  }
  if (kind === 'pick-target') {
    openLinkTargetPicker();
  }
}

function loadSlashCommandUsage() {
  if (typeof window === 'undefined') return {};
  try {
    return parseNoteSlashUsage(window.localStorage.getItem(NOTE_SLASH_USAGE_STORAGE_KEY));
  } catch {
    return {};
  }
}

function recordSlashCommandUsage(commandKey) {
  slashCommandUsage.value = incrementNoteSlashUsage(slashCommandUsage.value, commandKey);
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(
      NOTE_SLASH_USAGE_STORAGE_KEY,
      JSON.stringify(slashCommandUsage.value),
    );
  } catch {
    // Befehle bleiben auch ohne verfügbaren Local Storage vollständig nutzbar.
  }
}

function docPickerItems() {
  // Echte Dokumente (Workspace) oder Mock (Prüfstand).
  if (Array.isArray(props.documentItems)) return props.documentItems;
  return MOCK_DOCUMENTS.map(d => ({ id: d.id, label: d.title, type: 'document', hint: d.correspondent, _doc: d }));
}

function linkTargetItems() {
  if (Array.isArray(props.linkTargets)) return props.linkTargets;
  if (Array.isArray(props.documentItems)) return props.documentItems; // Dokumente als Ziele
  return mockLinkTargets();
}

function openDocumentChipPicker() {
  const ed = editor.value;
  if (!ed) return;
  openPicker('document', docPickerItems(), (item) =>
    ed.chain().focus().insertDocumentChip({ docId: item.id, title: item.label }).run());
}

function openLinkTargetPicker() {
  const ed = editor.value;
  if (!ed) return;
  openPicker('target', linkTargetItems(), (item) =>
    ed.chain().focus().insertWikiLink({
      targetType: item.type,
      targetId: item.id,
      label: item.label,
    }).run());
}

/* ── Gemeinsame Editor-Tastatursteuerung ────────────────────────────────── */
function onEditorKeyDown(event) {
  if (
    (event.metaKey || event.ctrlKey)
    && !event.altKey
    && !event.shiftKey
    && event.key.toLowerCase() === 'k'
  ) {
    event.preventDefault();
    openLinkEditor();
    return true;
  }

  // Cmd/Ctrl + / öffnet die Tastenkürzel-Übersicht.
  if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key === '/') {
    event.preventDefault();
    openShortcuts();
    return true;
  }

  if (cleanup.open && event.key === 'Escape') {
    event.preventDefault();
    discardCleanup();
    return true;
  }

  if (tableMenu.open && handleTableKeydown(event)) return true;

  // Picker (Beleg-/Ziel-Auswahl) hat Vorrang.
  if (picker.open) return handlePickerKeydown(event);

  if (!slash.open || !slashMenuEntries.value.length) return false;
  const entries = slashMenuEntries.value;
  const n = entries.length;
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    event.stopPropagation();
    moveSlashSelection(1, n);
    return true;
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault();
    event.stopPropagation();
    moveSlashSelection(-1, n);
    return true;
  }
  if (event.key === 'Enter' || event.key === 'Tab') {
    event.preventDefault();
    event.stopPropagation();
    const entry = entries[slash.index] || entries[0];
    runSlash(entry.command);
    return true;
  }
  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    slash.open = false;
    return true;
  }
  return false;
}

function moveSlashSelection(step, itemCount) {
  slash.index = (slash.index + step + itemCount) % itemCount;
  nextTick(() => {
    const menu = slashMenuEl.value;
    const activeItem = menu?.querySelector(`[data-slash-index="${slash.index}"]`);
    if (!menu || !activeItem) return;

    const menuRect = menu.getBoundingClientRect();
    const itemRect = activeItem.getBoundingClientRect();
    const inset = 6;
    if (itemRect.top < menuRect.top + inset) {
      menu.scrollTop -= menuRect.top + inset - itemRect.top;
    } else if (itemRect.bottom > menuRect.bottom - inset) {
      menu.scrollTop += itemRect.bottom - (menuRect.bottom - inset);
    }
    updateSlashSelection();
  });
}

function selectSlashIndex(index) {
  if (slash.index === index) return;
  slash.index = index;
}

function updateSlashSelection() {
  const menu = slashMenuEl.value;
  const activeItem = menu?.querySelector(`[data-slash-index="${slash.index}"]`);
  if (!slash.open || !menu || !activeItem) {
    slash.selectionVisible = false;
    return;
  }

  const menuRect = menu.getBoundingClientRect();
  const itemRect = activeItem.getBoundingClientRect();
  // Während der Öffnungsanimation ist das ganze Menü leicht skaliert. Die
  // Auswahl wird auf Layout-Pixel zurückgerechnet, damit sie auch im ersten
  // Animationsframe exakt über dem aktiven Eintrag liegt.
  const menuScale = menu.offsetWidth ? menuRect.width / menu.offsetWidth : 1;
  slash.selectionStyle = {
    height: `${itemRect.height / menuScale}px`,
    transform: `translateY(${(itemRect.top - menuRect.top) / menuScale + menu.scrollTop}px)`,
  };
  slash.selectionVisible = true;
}

// Index klemmen, wenn Filter die Trefferzahl verkleinert.
watch(slashResults, (r) => {
  if (slash.index >= r.length) slash.index = 0;
  nextTick(updateSlashSelection);
});
watch(() => slash.index, () => nextTick(updateSlashSelection));
</script>

<style scoped>
.note-editor {
  display: flex;
  flex-direction: column;
  min-height: 0;
  --note-editor-font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  /* Differenzierter vertikaler Rhythmus:
     - paragraph-gap: Abstand zwischen aufeinanderfolgenden Absätzen. Bewusst
       moderat, damit EIN Enter als eine klare Absatztrennung liest (nicht als
       Doppelumbruch; Browser-Standardmargen sind über margin-block:0 neutral).
     - block-gap: ein gemeinsamer Außenabstand für alle Strukturelemente –
       unabhängig davon, ob es sich um Überschrift, Liste, Tabelle, Bild,
       Layout, Hinweis- oder Schnellblock handelt. */
  --note-editor-paragraph-gap: 0.5em;
  --note-editor-block-gap: 1.75rem;
  --note-editor-heading-gap: 0.75rem;
}

.note-editor--font-serif {
  --note-editor-font-family: Georgia, "Times New Roman", serif;
}

.note-editor--font-mono {
  --note-editor-font-family: ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, monospace;
}

.note-editor--spacing-compact {
  --note-editor-paragraph-gap: 0.3em;
  --note-editor-block-gap: 1.25rem;
}

.note-editor--spacing-spacious {
  --note-editor-paragraph-gap: 0.75em;
  --note-editor-block-gap: 2.1rem;
}

.note-editor__title {
  border: 0;
  background: transparent;
  outline: none;
  width: 100%;
  font-family: var(--note-editor-font-family);
  font-weight: 500;
  font-size: clamp(1.7rem, 3.4vw, 2.3rem);
  line-height: 1.12;
  letter-spacing: -0.01em;
  color: var(--pm-text, #0e181b);
  padding: 4px 0 10px;
}

.note-editor__title::placeholder { color: var(--pm-muted, #8a969b); opacity: 0.55; }

.note-editor__surface {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  cursor: text;
}

/* ── Eingebettete Workspace-Variante ────────────────────────────────────── */

.note-editor--workspace {
  min-height: 100%;
  background: var(--pm-content-surface, #fff);
}

.note-editor--workspace .note-editor__surface {
  min-height: 420px;
  padding: 24px clamp(28px, 5vw, 58px) 88px;
}

/* Im Vollbild nutzt die Schreibfläche den zusätzlichen Platz. Der feste,
   beidseitig gleiche Gutter hält Text, Listen und breite Blöcke nah an der
   Editor-Kante, ohne die kompakteren Split-View-Breiten zu verändern. */

.note-editor--workspace.is-fullscreen .note-editor__surface {
  padding-inline: 28px;
}

.note-editor__image-input {
  position: fixed;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  white-space: nowrap;
}

.note-editor__image-status {
  position: absolute;
  z-index: 8;
  top: 14px;
  right: clamp(18px, 3vw, 34px);
  display: inline-flex;
  max-width: min(360px, calc(100% - 36px));
  align-items: center;
  gap: 8px;
  padding: 8px 11px;
  border: 1px solid color-mix(in srgb, var(--pm-accent, #006b75) 24%, var(--pm-divider, #d8dfe1));
  border-radius: 9px;
  background: var(--pm-app-surface-raised, #fff);
  box-shadow: 0 5px 18px rgba(16, 38, 42, 0.11);
  color: var(--pm-accent-strong, #00555f);
  font-size: 0.78rem;
  line-height: 1.3;
  pointer-events: none;
}

.note-editor__image-status.is-error {
  border-color: color-mix(in srgb, #b93e3e 34%, var(--pm-divider, #d8dfe1));
  color: #9c3030;
}

.note-editor__image-spinner {
  width: 14px;
  height: 14px;
  flex: none;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: pm-ai-spin 700ms linear infinite;
}

.note-editor__writing {
  position: relative;
}

.note-editor--workspace .note-editor__writing {
  width: 100%;
  max-width: 76ch;
  font-family: var(--note-editor-font-family);
  font-size: clamp(1rem, 1.5vw, 1.13rem);
}

.note-editor--workspace.note-editor--width-compact .note-editor__writing {
  max-width: 58ch;
}

.note-editor--workspace.note-editor--width-wide .note-editor__writing {
  max-width: 92ch;
}

.note-editor--workspace.is-fullscreen .note-editor__writing {
  max-width: none;
  margin-inline: 0;
}

.note-editor__empty-hint {
  position: absolute;
  z-index: 1;
  top: 0;
  left: 0;
  display: grid;
  gap: 8px;
  max-width: min(100%, 520px);
  color: var(--pm-muted, #748084);
  opacity: 0;
  pointer-events: none;
  user-select: none;
}

.note-editor__empty-hint.is-positioned {
  opacity: 1;
  animation: note-editor-empty-hint-in 180ms var(--pm-easing, ease-out) both;
}

.note-editor__empty-hint-title {
  font-size: clamp(0.94rem, 1.25vw, 1.02rem);
  font-weight: 520;
  line-height: 1.4;
  letter-spacing: -0.005em;
}

.note-editor__empty-hint-detail {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: color-mix(in srgb, var(--pm-muted, #748084) 76%, transparent);
  font-size: 0.76rem;
  line-height: 1.35;
}

.note-editor__empty-hint-detail kbd {
  display: inline-grid;
  min-width: 22px;
  height: 22px;
  padding-inline: 6px;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--pm-muted, #748084) 28%, transparent);
  border-radius: 6px;
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 94%, var(--pm-muted, #748084) 6%);
  box-shadow: 0 1px 0 color-mix(in srgb, var(--pm-muted, #748084) 20%, transparent);
  color: var(--pm-muted, #657176);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.76rem;
  font-weight: 650;
  line-height: 1;
}

@keyframes note-editor-empty-hint-in {
  from { opacity: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .note-editor__empty-hint {
    animation: none;
  }
}

:global(.pm-no-animations) .note-editor__empty-hint {
  animation: none;
}

.note-editor--workspace :deep(.pm-content) {
  max-width: 76ch;
  min-height: 340px;
  font-size: clamp(1rem, 1.5vw, 1.13rem);
  /* Ausgewogene Zeilenhöhe: Der Browser leitet die Höhe der Schreibmarke aus
     der line-height ab (es gibt kein separates caret-height). Bei 1.68/1.7 wirkte
     die Caret deutlich zu hoch. Chromium zeichnet die Caret am Ende des letzten
     Blocks in Schrifthöhe, sonst in Zeilenhöhe – der sichtbare Unterschied ist das
     Leading (line-height − Schrifthöhe). 1.35 hält es klein (~3px) und lesbar. */
  line-height: 1.35;
}

/* ── Fließtext (ProseMirror) ─────────────────────────────────────────────── */

.note-editor :deep(.pm-content) {
  outline: none;
  color: var(--pm-text, #0e181b);
  font-family: var(--note-editor-font-family);
  font-size: 1.0625rem;
  line-height: 1.35;
  max-width: 68ch;
  caret-color: var(--pm-accent, #006b75);
}

.note-editor--workspace.note-editor--width-compact :deep(.pm-content) {
  max-width: 58ch;
}

.note-editor--workspace.note-editor--width-comfortable :deep(.pm-content) {
  max-width: 76ch;
}

.note-editor--workspace.note-editor--width-wide :deep(.pm-content) {
  max-width: 92ch;
}

.note-editor--workspace.is-fullscreen :deep(.pm-content) {
  box-sizing: border-box;
  width: 100%;
  max-width: none;
}

.note-editor :deep(.pm-content > *) {
  /* Browser-Margen würden zusätzlich zum konfigurierten Abstand wirken und
     einen einzelnen neuen Absatz wie zwei Zeilenumbrüche erscheinen lassen. */
  margin-block: 0;
}

.note-editor :deep(.pm-content > * + *) { margin-top: var(--note-editor-paragraph-gap); }

/* Frei platzierbare Spaltenblöcke. Ihre Höhe entsteht ausschließlich aus dem
   Inhalt; ober- und unterhalb bleiben normale Editorblöcke möglich. */

.note-editor :deep([data-page-layout]) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: stretch;
  width: 100%;
}

.note-editor :deep([data-page-layout][data-columns="1"]) { grid-template-columns: minmax(0, 1fr); }

.note-editor :deep([data-page-layout][data-columns="2"]) { grid-template-columns: repeat(2, minmax(0, 1fr)); }

.note-editor :deep([data-page-layout][data-columns="3"]) { grid-template-columns: repeat(3, minmax(0, 1fr)); }

.note-editor :deep([data-page-layout][data-columns="4"]) { grid-template-columns: repeat(4, minmax(0, 1fr)); }

.note-editor :deep([data-page-layout][data-columns="5"]) { grid-template-columns: repeat(5, minmax(0, 1fr)); }

.note-editor :deep([data-layout-column]) {
  min-width: 0;
  padding: 2px clamp(10px, 1.5vw, 22px);
  overflow-wrap: anywhere;
  cursor: text;
}

.note-editor :deep([data-layout-column] + [data-layout-column]) {
  border-left: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 82%, transparent);
}

.note-editor :deep([data-layout-column]:first-child) { padding-left: 0; }

.note-editor :deep([data-layout-column]:last-child) { padding-right: 0; }

.note-editor :deep([data-layout-column] > *) { margin-block: 0; }

.note-editor :deep([data-layout-column] > * + *) { margin-top: var(--note-editor-paragraph-gap); }

.note-editor :deep([data-layout-column] > p:only-child:has(> br.ProseMirror-trailingBreak)::before) {
  content: 'In dieser Spalte schreiben …';
  float: left;
  height: 0;
  color: var(--pm-muted, #8a969b);
  opacity: 0.52;
  pointer-events: none;
}

.note-editor :deep(mark.pm-text-highlight) {
  padding-inline: 0.06em;
  border-radius: 0.16em;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}

@media (max-width: 760px) {
  .note-editor :deep([data-page-layout]) { grid-template-columns: 1fr !important; }
  .note-editor :deep([data-layout-column]) {
    padding: 18px 0;
  }
  .note-editor :deep([data-layout-column]:first-child) { padding-top: 0; }
  .note-editor :deep([data-layout-column] + [data-layout-column]) {
    border-top: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 82%, transparent);
    border-left: 0;
  }
}

.note-editor :deep(.pm-content h1) {
  font-family: inherit; font-weight: 600;
  font-size: 1.55rem; line-height: 1.2; letter-spacing: -0.01em;
}

.note-editor :deep(.pm-content h2) {
  font-family: inherit; font-weight: 600;
  font-size: 1.28rem; line-height: 1.25;
}

.note-editor :deep(.pm-content h3) { font-weight: 600; font-size: 1.08rem; }

.note-editor :deep(.pm-content h4) { font-weight: 600; font-size: 1rem; }

/* Einheitliche Block-Rhythmik: Sobald mindestens eine Seite der Trennung kein
   normaler Absatz ist, gilt der großzügigere Strukturabstand. Damit werden
   auch NodeViews wie Tabellen, Bilder, Layouts, Hinweis-, KI- und Schnellblöcke
   automatisch erfasst, ohne eine fragile Liste von Knotentypen zu pflegen. */

.note-editor :deep(.pm-content > * + :not(p)),
.note-editor :deep(.pm-content > :not(p) + *) {
  margin-top: var(--note-editor-block-gap);
}

.note-editor :deep([data-layout-column] > * + :not(p)),
.note-editor :deep([data-layout-column] > :not(p) + *) {
  margin-top: var(--note-editor-block-gap);
}

/* Überschriften bilden bewusst eine ruhigere Ausnahme von der Block-Rhythmik:
   unabhängig von Ebene und Nachbar bleibt ihr Abstand auf beiden Seiten gleich. */

.note-editor :deep(.pm-content > * + :is(h1, h2, h3, h4, h5, h6)), .note-editor :deep(.pm-content > :is(h1, h2, h3, h4, h5, h6) + *), .note-editor :deep([data-layout-column] > * + :is(h1, h2, h3, h4, h5, h6)), .note-editor :deep([data-layout-column] > :is(h1, h2, h3, h4, h5, h6) + *) {
  margin-top: var(--note-editor-heading-gap);
}

.note-editor :deep(.pm-content > :is(h1, h2, h3, h4, h5, h6):first-child), .note-editor :deep([data-layout-column] > :is(h1, h2, h3, h4, h5, h6):first-child) {
  margin-top: 0;
}

.note-editor :deep(.pm-content ul),
.note-editor :deep(.pm-content ol) { padding-left: 1.4em; }

.note-editor :deep(.pm-content li) { margin: 0.2em 0; }

.note-editor :deep(.pm-content blockquote) {
  border-left: 2.5px solid var(--pm-accent, #006b75);
  padding-left: 0.9em; margin-left: 0; color: var(--pm-muted, #535e62); font-style: italic;
}

.note-editor :deep(.pm-content code) {
  font-family: 'IBM Plex Mono', ui-monospace, monospace; font-size: 0.86em;
  background: rgba(var(--v-theme-primary, 0 107 117), 0.1);
  color: var(--pm-accent-strong, #00555f); padding: 1px 5px; border-radius: 5px;
}

.note-editor :deep(.pm-content pre) {
  background: var(--pm-viewer-surface, #eef2f4);
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 10px; padding: 12px 14px; overflow-x: auto;
}

.note-editor :deep(.pm-content pre code) { background: none; color: inherit; padding: 0; }

.note-editor :deep(.pm-content hr) {
  border: 0; height: 1px; background: var(--pm-divider, #d8dfe1); margin-inline: 0;
}

.note-editor :deep(.pm-content a) {
  color: var(--pm-accent-strong, #00555f);
  cursor: pointer;
  text-decoration-color: color-mix(in srgb, var(--pm-accent-strong, #00555f) 72%, transparent);
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
}

/* Rückgängig/Wiederholen: markiert nur die tatsächlich geänderte Stelle. */

.note-editor :deep(.pm-history-flash) {
  border-radius: 3px;
  animation: pm-history-change-flash 720ms ease-out both;
}

@keyframes pm-history-change-flash {
  0% {
    background: color-mix(in srgb, var(--pm-accent, #006b75) 22%, transparent);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--pm-accent, #006b75) 7%, transparent);
  }
  100% { background: transparent; box-shadow: 0 0 0 0 transparent; }
}

/* Task-Listen */

.note-editor :deep(.pm-content ul[data-type="taskList"]) { list-style: none; padding-left: 0.2em; }

.note-editor :deep(.pm-content ul[data-type="taskList"] li) { display: flex; gap: 0.55em; align-items: flex-start; }

.note-editor :deep(.pm-content ul[data-type="taskList"] li > label) {
  display: grid;
  place-items: center;
  height: 1.35em;
  margin: 0;
}

.note-editor :deep(.pm-content ul[data-type="taskList"] input[type="checkbox"]) {
  appearance: none;
  -webkit-appearance: none;
  width: 1.05rem;
  height: 1.05rem;
  margin: 0;
  border: 1.5px solid color-mix(in srgb, var(--pm-muted, #748084) 72%, transparent);
  border-radius: 50%;
  background: transparent;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
}

.note-editor :deep(.pm-content ul[data-type="taskList"] input[type="checkbox"]:hover) {
  border-color: var(--pm-accent, #006b75);
}

.note-editor :deep(.pm-content ul[data-type="taskList"] input[type="checkbox"]:checked) {
  border-color: var(--pm-accent, #006b75);
  background: var(--pm-accent, #006b75);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='m4 8 2.5 2.5L12 5' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-position: center;
  background-size: 0.85rem 0.85rem;
  background-repeat: no-repeat;
}

.note-editor :deep(.pm-content ul[data-type="taskList"] input[type="checkbox"]:focus-visible) {
  outline: 2px solid color-mix(in srgb, var(--pm-accent, #006b75) 35%, transparent);
  outline-offset: 2px;
}

.note-editor :deep(.pm-content ul[data-type="taskList"] input[type="checkbox"]:disabled) {
  cursor: default;
}

/* Strukturierte Tabellen: horizontal scrollbar, in der Breite ruhig und im
   Darkmode vollständig über die PaperMind-Tokens eingefärbt. */

.note-editor :deep(.pm-content .tableWrapper) {
  max-width: 100%;
  overflow-x: auto;
  border-radius: 10px;
  scrollbar-color: color-mix(in srgb, var(--pm-muted, #535e62) 32%, transparent) transparent;
  scrollbar-width: thin;
}

.note-editor :deep(.pm-content table) {
  width: 100%;
  min-width: 420px;
  overflow: hidden;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-collapse: separate;
  border-spacing: 0;
  border-radius: 10px;
  table-layout: fixed;
}

.note-editor :deep(.pm-content th),
.note-editor :deep(.pm-content td) {
  position: relative;
  box-sizing: border-box;
  min-width: 96px;
  padding: 9px 11px;
  border-right: 1px solid var(--pm-divider, #d8dfe1);
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
  vertical-align: top;
}

.note-editor :deep(.pm-content th:last-child),
.note-editor :deep(.pm-content td:last-child) { border-right: 0; }

.note-editor :deep(.pm-content tr:last-child > *) { border-bottom: 0; }

.note-editor :deep(.pm-content th) {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 9%, var(--pm-app-surface, #fff));
  color: var(--pm-text, #0e181b);
  font-weight: 680;
  text-align: left;
}

.note-editor :deep(.pm-content td) {
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 96%, transparent);
}

.note-editor :deep(.pm-content th > p),
.note-editor :deep(.pm-content td > p) { margin: 0; }

.note-editor :deep(.pm-content .selectedCell::after) {
  position: absolute;
  z-index: 2;
  inset: 0;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 13%, transparent);
  content: '';
  pointer-events: none;
}

.note-editor :deep(.pm-content .column-resize-handle) {
  position: absolute;
  z-index: 3;
  top: 0;
  right: -2px;
  bottom: 0;
  width: 4px;
  background: var(--pm-accent, #006b75);
  pointer-events: none;
}

.note-editor :deep(.pm-content.resize-cursor) { cursor: col-resize; }

/* Placeholder */

.note-editor :deep(.pm-content p.is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  float: left; height: 0; pointer-events: none;
  color: var(--pm-muted, #8a969b); opacity: 0.6;
}

.note-editor--workspace :deep(.pm-content p.is-editor-empty:first-child::before) {
  content: none;
}

/* ── Schwebende Menüs ────────────────────────────────────────────────────── */

/* Auswahl-Bubble: bewusst dunkel & kompakt – hebt sich klar von der hellen,
   persistenten Formatierungsleiste ab (kontextuell statt Chrome). Der dunkle
   Look bleibt in beiden Themes gleich; Rahmen + Schatten trennen ihn vom Grund. */

.pm-bubble__row { display: flex; align-items: center; gap: 1px; }

.pm-bubble__btn {
  border: 0; background: transparent; cursor: pointer;
  min-width: 28px; height: 26px; padding: 0 6px; border-radius: 6px;
  display: grid; place-items: center;
  color: #e4e2da; font-size: 0.9rem;
  transition: background 120ms ease, color 120ms ease;
}

.pm-bubble__btn:hover { background: rgba(255, 255, 255, 0.10); color: #fff; }

.pm-bubble__btn.is-active { background: rgba(255, 255, 255, 0.17); color: #fff; }

.pm-bubble__btn:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.6);
  outline-offset: -2px;
}

.pm-bubble__btn.is-ai { color: #7fe0c1; }

.pm-bubble__btn:not(.is-ai) + .pm-bubble__btn.is-ai {
  margin-left: 3px;
  padding-left: 9px;
  border-left: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 0 6px 6px 0;
}

.pm-bubble__btn.is-ai:hover { background: rgba(127, 224, 193, 0.15); color: #9fe9d4; }

.pm-bubble__swatches {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 4px 2px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.pm-bubble__swatch {
  width: 18px; height: 18px; padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 5px;
  background: var(--pm-swatch, #fde68a);
  cursor: pointer;
  display: grid; place-items: center;
  transition: transform 100ms ease, box-shadow 100ms ease;
}

.pm-bubble__swatch:hover { transform: scale(1.12); }

.pm-bubble__swatch.is-active { box-shadow: 0 0 0 2px #23241f, 0 0 0 3px #fff; }

.pm-bubble__swatch:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.85);
  outline-offset: 2px;
}

.pm-bubble__swatch--remove {
  background: transparent; color: #e4e2da;
  border-color: rgba(255, 255, 255, 0.22);
  margin-left: 2px;
}

.pm-bubble__swatch--remove:hover { background: rgba(255, 255, 255, 0.10); color: #fff; transform: none; }

.pm-bubble__swatch--remove:disabled { opacity: 0.4; cursor: default; }

/* Treffer der notizinternen Suche bleiben reine ProseMirror-Dekorationen und
   verändern weder Auswahl noch gespeicherten Dokumentinhalt. */

.note-editor :deep(.pm-note-search-match) {
  border-radius: 3px;
  background: color-mix(in srgb, var(--pm-warning, #d97706) 24%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--pm-warning, #d97706) 18%, transparent);
}

.note-editor :deep(.pm-note-search-match--active) {
  background: color-mix(in srgb, var(--pm-warning, #d97706) 48%, transparent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--pm-warning, #d97706) 38%, transparent);
}

/* ── Statuszeile ─────────────────────────────────────────────────────────── */

.note-editor__status {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 18px; padding-top: 12px;
  border-top: 1px solid var(--pm-divider, #d8dfe1);
  font-size: 0.78rem; color: var(--pm-muted, #535e62);
}

.note-editor__save { display: inline-flex; align-items: center; gap: 7px; }

.note-editor__dot { width: 7px; height: 7px; border-radius: 50%; background: var(--pm-muted, #9aa5aa); }

.note-editor__save.is-saving .note-editor__dot { background: var(--pm-accent, #006b75); animation: pm-pulse 1s ease-in-out infinite; }

.note-editor__save.is-saved .note-editor__dot { background: var(--pm-accent, #006b75); }

.note-editor__count { font-variant-numeric: tabular-nums; }

@keyframes pm-pulse { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }

@media (prefers-reduced-motion: reduce) {
  .note-editor__save.is-saving .note-editor__dot { animation: none; }
  .pm-bubble__btn { transition: none; }

  .note-editor__image-spinner { animation: none; }

  .note-editor :deep(.pm-history-flash) { animation: none; }
}

:global(.pm-no-animations) .note-editor :deep(.pm-history-flash) {
  animation: none;
}
</style>

<style scoped src="./styles/progress.css"></style>
<style scoped src="./styles/floating.css"></style>
<style scoped src="./styles/slashMenu.css"></style>
