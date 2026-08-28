<!--
  NoteEditor — M0 (editor-first): eine ruhige, papierartige Schreibfläche auf
  TipTap/ProseMirror. Persistenz-agnostisch: gibt Titel + Body-JSON nach außen,
  das Speichern (localStorage in M0, Backend ab M2) übernimmt der Aufrufer.

  Bewusst OHNE tippy/Teleport: Bubble- und Slash-Menü sind selbst positionierte
  Elemente INNERHALB von .papermind-app, damit die --pm-*-Kontur-Tokens greifen
  (vgl. Vuetify-Teleport-Token-Falle). Positionierung über posToDOMRect.
-->
<template>
  <div
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

    <div
      v-if="workspace"
      class="note-editor__toolbar"
      :class="{ 'is-ducked': toolbarDucked }"
      role="toolbar"
      aria-label="Text formatieren"
      :aria-disabled="readonly ? 'true' : undefined"
      :inert="readonly ? '' : undefined"
      @pointerenter="revealFormattingToolbar"
      @focusin="revealFormattingToolbar"
    >
      <div class="note-editor__toolbar-group">
        <button
          type="button"
          class="note-editor__toolbar-btn note-editor__toolbar-btn--text"
          :class="{ 'is-active': toolbarActive('heading', { level: 2 }) }"
          title="Überschrift 2"
          @click.prevent="runToolbar('h2')"
        >H2</button>
        <button
          type="button"
          class="note-editor__toolbar-btn note-editor__toolbar-btn--text"
          :class="{ 'is-active': toolbarActive('heading', { level: 3 }) }"
          title="Überschrift 3"
          @click.prevent="runToolbar('h3')"
        >H3</button>
        <button
          type="button"
          class="note-editor__toolbar-btn note-editor__toolbar-btn--text"
          :class="{ 'is-active': toolbarActive('heading', { level: 4 }) }"
          title="Überschrift 4"
          @click.prevent="runToolbar('h4')"
        >H4</button>
        <button
          type="button"
          class="note-editor__toolbar-btn note-editor__toolbar-btn--wide"
          :class="{ 'is-active': toolbarActive('paragraph') }"
          title="Fließtext"
          @click.prevent="runToolbar('paragraph')"
        >Text</button>
      </div>

      <span class="note-editor__toolbar-divider" aria-hidden="true" />

      <div class="note-editor__toolbar-group">
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('bold') }"
          title="Fett"
          aria-label="Fett"
          @click.prevent="runToolbar('bold')"
        ><strong>B</strong></button>
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('italic') }"
          title="Kursiv"
          aria-label="Kursiv"
          @click.prevent="runToolbar('italic')"
        ><em>I</em></button>
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('underline') }"
          title="Unterstrichen"
          aria-label="Unterstrichen"
          @click.prevent="runToolbar('underline')"
        ><u>U</u></button>
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('code') }"
          title="Code"
          aria-label="Code"
          @click.prevent="runToolbar('code')"
        ><span class="note-editor__toolbar-code">A</span></button>
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('link') }"
          title="Hyperlink (⌘/Strg+K)"
          aria-label="Hyperlink einfügen oder bearbeiten"
          @click.prevent="openLinkEditor"
        ><v-icon size="18">mdi-link-variant</v-icon></button>
      </div>

      <span class="note-editor__toolbar-divider" aria-hidden="true" />

      <div class="note-editor__toolbar-group">
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('bulletList') }"
          title="Aufzählung"
          aria-label="Aufzählung"
          @click.prevent="runToolbar('bulletList')"
        ><v-icon size="18">mdi-format-list-bulleted</v-icon></button>
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('orderedList') }"
          title="Nummerierte Liste"
          aria-label="Nummerierte Liste"
          @click.prevent="runToolbar('orderedList')"
        ><v-icon size="18">mdi-format-list-numbered</v-icon></button>
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('blockquote') }"
          title="Zitat"
          aria-label="Zitat"
          @click.prevent="runToolbar('blockquote')"
        ><v-icon size="18">mdi-format-quote-close</v-icon></button>
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('codeBlock') }"
          title="Codeblock"
          aria-label="Codeblock"
          @click.prevent="runToolbar('codeBlock')"
        ><span class="note-editor__toolbar-braces">{ }</span></button>
        <button
          type="button"
          class="note-editor__toolbar-btn"
          :class="{ 'is-active': toolbarActive('table') }"
          title="Tabelle"
          aria-label="Tabelle einfügen oder bearbeiten"
          @click.prevent="openTableMenu"
        ><v-icon size="18">mdi-table</v-icon></button>
      </div>

      <template v-if="aiAvailable">
        <span class="note-editor__toolbar-divider" aria-hidden="true" />
        <div class="note-editor__toolbar-group">
          <button
            type="button"
            class="note-editor__toolbar-btn"
            title="Mit KI schreiben"
            aria-label="Mit KI schreiben"
            @click.prevent="openAIPrompt"
          ><v-icon size="18">mdi-auto-fix</v-icon></button>
        </div>
      </template>

    </div>

    <div
      ref="surfaceEl"
      class="note-editor__surface"
      @pointerdown="focusEditorEndFromWhitespace"
      @pointermove.passive="trackTableHandle"
      @pointerleave="clearHoveredTable"
    >
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
            <span>für Überschriften, Listen und weitere Bausteine</span>
          </span>
        </div>
      </div>

      <button
        v-if="editor && tableHandle.visible"
        type="button"
        class="pm-table-handle"
        :class="{ 'is-open': tableMenu.open && tableMenu.mode === 'edit' }"
        :style="tableHandle.style"
        aria-label="Tabellenaktionen öffnen"
        title="Tabellenaktionen"
        @pointermove.stop
        @mousedown.stop.prevent="openTableMenuFromHandle"
      >
        <v-icon size="18">mdi-dots-vertical</v-icon>
      </button>

      <!-- Auswahl-Formatierung -->
      <div
        v-if="editor && bubble.show"
        ref="bubbleEl"
        class="pm-float pm-bubble"
        :style="bubble.style"
        role="toolbar"
        aria-label="Formatierung"
      >
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
          <span class="pm-bubble__glyph" v-html="b.glyph"></span>
        </button>
      </div>

      <!-- Klassischer externer Hyperlink. Interne PaperMind-Ziele bleiben
           bewusst dem [[Verweis]]-Element vorbehalten. -->
      <form
        v-if="editor && linkEditor.open"
        class="pm-float pm-link-editor"
        :style="linkEditor.style"
        aria-label="Hyperlink bearbeiten"
        @submit.prevent="applyLink"
        @mousedown.stop
      >
        <div class="pm-link-editor__head">
          <span><v-icon size="17">mdi-link-variant</v-icon> Hyperlink</span>
          <kbd>⌘K</kbd>
        </div>
        <div class="pm-link-editor__input-row">
          <input
            ref="linkInputEl"
            v-model="linkEditor.href"
            type="text"
            inputmode="url"
            autocomplete="url"
            spellcheck="false"
            placeholder="https://… oder name@domain.de"
            :aria-invalid="linkEditor.error ? 'true' : undefined"
            @input="linkEditor.error = ''; linkEditor.copied = false"
            @keydown.esc.prevent="closeLinkEditor(true)"
          />
          <button type="submit" class="pm-link-editor__save" aria-label="Hyperlink übernehmen">
            <v-icon size="18">mdi-check</v-icon>
          </button>
        </div>
        <div v-if="linkEditor.error" class="pm-link-editor__error" role="alert">{{ linkEditor.error }}</div>
        <div v-if="linkEditor.existing" class="pm-link-editor__actions">
          <button type="button" @click="openLinkTarget">
            <v-icon size="16">mdi-open-in-new</v-icon><span>Öffnen</span>
          </button>
          <button type="button" @click="copyLinkTarget">
            <v-icon size="16">mdi-content-copy</v-icon><span>{{ linkEditor.copied ? 'Kopiert' : 'Kopieren' }}</span>
          </button>
          <button type="button" class="is-danger" @click="removeLink">
            <v-icon size="16">mdi-link-off</v-icon><span>Entfernen</span>
          </button>
        </div>
      </form>

      <!-- Slash-Menü -->
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

      <!-- Tabellenwahl und kompakte Werkzeuge für die aktive Tabellenzelle. -->
      <div
        v-if="editor && tableMenu.open"
        class="pm-float pm-table-menu"
        :style="tableMenu.style"
        :aria-label="tableMenu.mode === 'insert' ? 'Tabelle einfügen' : 'Tabelle bearbeiten'"
        @mousedown.stop
      >
        <template v-if="tableMenu.mode === 'insert'">
          <div class="pm-table-menu__head">
            <span>Tabelle einfügen</span>
            <strong>{{ tableMenu.rows }} × {{ tableMenu.cols }}</strong>
          </div>
          <div class="pm-table-menu__grid" role="grid" aria-label="Tabellengröße wählen">
            <button
              v-for="cell in TABLE_PICKER_CELLS"
              :key="`${cell.row}:${cell.col}`"
              type="button"
              class="pm-table-menu__cell"
              :class="{ 'is-selected': cell.row <= tableMenu.rows && cell.col <= tableMenu.cols }"
              :aria-label="`${cell.row} Zeilen und ${cell.col} Spalten`"
              @mouseenter="selectTableSize(cell.row, cell.col)"
              @focus="selectTableSize(cell.row, cell.col)"
              @mousedown.prevent="insertTable(cell.row, cell.col)"
            ></button>
          </div>
          <div class="pm-table-menu__header-options" role="radiogroup" aria-label="Tabellenkopf wählen">
            <button
              type="button"
              class="pm-table-menu__header-toggle"
              :class="{ 'is-active': tableMenu.withHeaderRow }"
              role="radio"
              :aria-checked="tableMenu.withHeaderRow"
              @mousedown.prevent="selectTableHeaderMode('row')"
            >
              <v-icon size="17">mdi-table-headers-eye</v-icon>
              Erste Zeile als Kopfzeile
            </button>
            <button
              type="button"
              class="pm-table-menu__header-toggle"
              :class="{ 'is-active': tableMenu.withHeaderColumn }"
              role="radio"
              :aria-checked="tableMenu.withHeaderColumn"
              @mousedown.prevent="selectTableHeaderMode('column')"
            >
              <v-icon size="17">mdi-table-column</v-icon>
              Erste Spalte als Kopfspalte
            </button>
          </div>
        </template>

        <template v-else>
          <div class="pm-table-menu__head">
            <span>Tabelle bearbeiten</span>
          </div>
          <div class="pm-table-menu__actions">
            <button type="button" @mousedown.prevent="runTableCommand('addRowAfter')">
              <v-icon size="18">mdi-table-row-plus-after</v-icon><span>Zeile darunter</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('addColumnAfter')">
              <v-icon size="18">mdi-table-column-plus-after</v-icon><span>Spalte rechts</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('toggleHeaderRow')">
              <v-icon size="18">mdi-table-headers-eye</v-icon><span>Kopfzeile umschalten</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('toggleHeaderColumn')">
              <v-icon size="18">mdi-table-column</v-icon><span>Kopfspalte umschalten</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('deleteRow')">
              <v-icon size="18">mdi-table-row-remove</v-icon><span>Zeile löschen</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('deleteColumn')">
              <v-icon size="18">mdi-table-column-remove</v-icon><span>Spalte löschen</span>
            </button>
            <button type="button" class="is-danger" @mousedown.prevent="runTableCommand('deleteTable')">
              <v-icon size="18">mdi-table-remove</v-icon><span>Tabelle löschen</span>
            </button>
          </div>
        </template>
      </div>

      <!-- Beleg-/Ziel-Picker (aus /beleg, /zitat, /verweis oder [[) -->
      <div
        v-if="editor && picker.open && filteredPicker.length"
        class="pm-float pm-slash pm-picker"
        :style="picker.style"
        role="listbox"
        :aria-label="pickerHint()"
      >
        <div class="pm-slash__hint">{{ pickerHint() }}</div>
        <button
          v-for="(it, i) in filteredPicker"
          :key="it.type + ':' + it.id"
          type="button"
          class="pm-slash__item"
          :class="{ 'is-active': i === picker.index }"
          role="option"
          :aria-selected="i === picker.index"
          @mousemove="picker.index = i"
          @mousedown.prevent="pickItem(it)"
        >
          <span class="pm-slash__chip">{{ pickerChip(it) }}</span>
          <span class="pm-slash__text">
            <span class="pm-slash__label">{{ it.label }}</span>
            <span class="pm-slash__desc">{{ it.hint }}</span>
          </span>
        </button>
      </div>

      <!-- Schlanker Prompt direkt an der Einfügeposition. Nur Notiztext wird
           übertragen; Dokumentkontext ist ein separater, lokal erzwungener Pfad. -->
      <form
        v-if="editor && aiPrompt.open"
        class="pm-float pm-ai-prompt"
        :class="{ 'is-generating': aiPrompt.loading }"
        :style="aiPrompt.style"
        :aria-label="aiPrompt.mode === 'selection' ? 'Auswahl mit KI bearbeiten' : 'Mit KI schreiben'"
        @submit.prevent="generateAIText"
      >
        <div class="pm-ai-prompt__head">
          <span>
            <v-icon class="pm-ai-prompt__icon" size="17" aria-hidden="true">mdi-auto-fix</v-icon>
            {{ aiPrompt.mode === 'selection' ? 'Auswahl mit KI bearbeiten' : 'Mit KI schreiben' }}
          </span>
          <button type="button" class="pm-ai-prompt__close" aria-label="Schließen" @click="closeAIPrompt">×</button>
        </div>
        <div class="pm-ai-prompt__context" :class="{ 'is-selection': aiPrompt.mode === 'selection' }">
          <span aria-hidden="true"></span>
          {{ aiContextLabel }}
        </div>
        <div class="pm-ai-prompt__input-row">
          <input
            ref="aiPromptInputEl"
            v-model="aiPrompt.instruction"
            type="text"
            maxlength="2000"
            autocomplete="off"
            :placeholder="aiPrompt.mode === 'selection' ? 'Was soll PaperMind mit der Auswahl tun?' : 'Was soll PaperMind schreiben?'"
            :disabled="aiPrompt.loading"
            @keydown.esc.prevent="closeAIPrompt"
          />
          <button
            type="submit"
            class="pm-ai-prompt__submit"
            :disabled="aiPrompt.loading || !aiPrompt.instruction.trim() || aiSelectionTooLong"
            :aria-label="aiPrompt.loading ? 'Text wird generiert' : 'Text generieren'"
          >
            <span v-if="aiPrompt.loading" class="pm-ai-prompt__spinner" aria-hidden="true"></span>
            <span v-else aria-hidden="true">→</span>
          </button>
        </div>
        <div v-if="aiPrompt.loading" class="pm-ai-prompt__progress" aria-hidden="true">
          <span></span>
        </div>
        <div
          v-if="!aiPrompt.loading && !aiPrompt.preview && visibleAIPromptSuggestions.length"
          class="pm-ai-prompt__suggestions"
        >
          <button
            v-for="suggestion in visibleAIPromptSuggestions"
            :key="suggestion"
            type="button"
            @click="applyAIPromptSuggestion(suggestion)"
          >{{ suggestion }}</button>
        </div>
        <div v-if="aiPrompt.preview" class="pm-ai-prompt__preview" aria-live="polite">
          <span>{{ aiPrompt.preview }}</span>
        </div>
        <div v-if="aiPrompt.loading" class="pm-ai-prompt__status" aria-live="polite">
          {{ aiPrompt.provider ? `${providerLabel(aiPrompt.provider)} · ${aiPrompt.model}` : 'Modell wird gestartet …' }}
        </div>
        <div
          v-if="aiPrompt.mode === 'selection' && aiPrompt.preview && !aiPrompt.loading && !aiPrompt.error"
          class="pm-ai-prompt__result-actions"
        >
          <button type="button" class="is-primary" @click="applySelectionAIResult('replace')">
            Auswahl ersetzen
          </button>
          <button type="button" @click="applySelectionAIResult('insert')">
            Danach einfügen
          </button>
        </div>
        <div v-if="aiPrompt.error" class="pm-ai-prompt__error" role="alert">{{ aiPrompt.error }}</div>
      </form>
    </div>

    <div v-if="!workspace" class="note-editor__status">
      <span class="note-editor__save" :class="`is-${status}`">
        <span class="note-editor__dot"></span>
        {{ saveLabel }}
      </span>
      <span class="note-editor__count">{{ words }} {{ words === 1 ? 'Wort' : 'Wörter' }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { EditorContent, useEditor, posToDOMRect } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import Document from '@tiptap/extension-document';
import Placeholder from '@tiptap/extension-placeholder';
import Typography from '@tiptap/extension-typography';
import TaskList from '@tiptap/extension-task-list';
import { PaperMindTaskItem } from './nodes/taskItemDue.js';
import { TableKit } from '@tiptap/extension-table';
import { isHistoryTransaction } from '@tiptap/pm/history';
import { DocumentChip } from './nodes/documentChip.js';
import { OcrQuote } from './nodes/ocrQuote.js';
import { AiBlock } from './nodes/aiBlock.js';
import { WikiLink } from './nodes/wikiLink.js';
import { Callout } from './nodes/callout.js';
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
import { MOCK_DOCUMENTS, mockLinkTargets, targetGlyph } from './mockData.js';
import { NOTE_CALLOUT_OPTIONS } from '../../utils/noteCallouts.js';
import { normalizeNoteHref, noteHrefLabel } from '../../utils/noteLinks.js';
import { streamNoteText } from '../../api/notes.js';
import { NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT } from '../../constants/promptDefaults.js';

const PaperMindDocument = Document.extend({
  addAttributes() {
    return {
      favorite: { default: false },
      linkedDocument: { default: null },
    };
  },
});

const props = defineProps({
  /** Body als ProseMirror-JSON-Dokument (oder null für leer). */
  modelValue: { type: Object, default: null },
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
  /** Konfigurierbare Schnellprompts im Fenster „Mit KI schreiben“ (maximal 6). */
  aiPromptSuggestions: {
    type: Array,
    default: () => [...NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT],
  },
  /** Echte Dokumente für /beleg (und /verweis-Ziele, falls keine linkTargets).
   *  Form: { id, label, type:'document', hint }. null → Mock-Daten (Prüfstand). */
  documentItems: { type: Array, default: null },
  /** Echte Verweis-Ziele für /verweis und [[…]]. null → aus documentItems bzw. Mock. */
  linkTargets: { type: Array, default: null },
});

const emit = defineEmits([
  'update:modelValue',
  'update:title',
  'change',
  'word-count',
  'history-checkpoint',
  'note-search-state',
]);

const surfaceEl = ref(null);
const writingEl = ref(null);
const titleEl = ref(null);
const aiPromptInputEl = ref(null);
const linkInputEl = ref(null);
const slashMenuEl = ref(null);
const bubbleEl = ref(null);
const words = ref(0);
const editorEmpty = ref(true);
const emptyHintPositioned = ref(false);
const emptyHintStyle = ref({ top: '0px', left: '0px' });
const toolbarDucked = ref(false);
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
let toolbarRevealTimer = null;
let toolbarScrollAnchor = 0;
let toolbarScrollRestoreFrame = null;
let restoringWorkspaceScroll = false;
let aiGenerationController = null;
let historyFlashTimer = null;
let linkCopiedTimer = null;
let emptyHintPositionFrame = null;
let emptyHintResizeObserver = null;

const TOOLBAR_DUCK_SCROLL_THRESHOLD = 24;
const TOOLBAR_REVEAL_DELAY_MS = 400;
const TABLE_PICKER_SIZE = 5;
const TABLE_PICKER_CELLS = Object.freeze(
  Array.from({ length: TABLE_PICKER_SIZE ** 2 }, (_, index) => ({
    row: Math.floor(index / TABLE_PICKER_SIZE) + 1,
    col: (index % TABLE_PICKER_SIZE) + 1,
  })),
);
const tableMenu = reactive({
  open: false,
  mode: 'insert',
  rows: 3,
  cols: 3,
  withHeaderRow: true,
  withHeaderColumn: false,
  anchorPos: null,
  style: {},
});
const tableHandle = reactive({
  visible: false,
  style: {},
});
let hoveredTableWrapper = null;
let activeTableWrapper = null;
const linkEditor = reactive({
  open: false,
  href: '',
  existing: false,
  copied: false,
  error: '',
  range: { from: 0, to: 0 },
  style: {},
});

/* ── Editor ──────────────────────────────────────────────────────────────── */
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
    PaperMindDocument,
    Placeholder.configure({ placeholder: props.placeholder }),
    Typography,
    TaskList,
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
    HistoryFlash,
    NoteSearch,
  ],
  editorProps: {
    attributes: { class: 'pm-content', spellcheck: props.spellcheckEnabled ? 'true' : 'false' },
    handleKeyDown: (_view, event) => onEditorKeyDown(event),
    handlePaste: (_view, event) => handleEditorPaste(event),
    handleClick: (view, _pos, event) => handleEditorLinkClick(view, event),
  },
  onUpdate: ({ editor: ed }) => {
    updateWordCount(ed);
    emit('update:modelValue', ed.getJSON());
    emit('change', { json: ed.getJSON(), text: ed.getText(), words: words.value });
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
  aiGenerationController?.abort();
  editor.value?.destroy();
  toolbarScrollContainer?.removeEventListener('scroll', onEditorScroll);
  window.removeEventListener('resize', refreshBubble);
  if (toolbarRevealTimer) window.clearTimeout(toolbarRevealTimer);
  if (toolbarScrollRestoreFrame) window.cancelAnimationFrame(toolbarScrollRestoreFrame);
  if (historyFlashTimer) window.clearTimeout(historyFlashTimer);
  if (linkCopiedTimer) window.clearTimeout(linkCopiedTimer);
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
  toolbarScrollAnchor = toolbarScrollContainer?.scrollTop || 0;
  toolbarScrollContainer?.addEventListener('scroll', onEditorScroll, { passive: true });
}

function applySpellcheck(enabled) {
  editor.value?.view?.dom?.setAttribute('spellcheck', enabled ? 'true' : 'false');
}

function onEditorScroll() {
  const scrollTop = toolbarScrollContainer?.scrollTop || 0;
  if (slash.open) refreshSlash();
  if (bubble.show) refreshBubble();
  if (restoringWorkspaceScroll) {
    toolbarScrollAnchor = scrollTop;
    return;
  }
  if (
    !toolbarDucked.value
    && Math.abs(scrollTop - toolbarScrollAnchor) < TOOLBAR_DUCK_SCROLL_THRESHOLD
  ) return;

  toolbarDucked.value = true;
  if (toolbarRevealTimer) window.clearTimeout(toolbarRevealTimer);
  toolbarRevealTimer = window.setTimeout(() => {
    toolbarDucked.value = false;
    toolbarScrollAnchor = toolbarScrollContainer?.scrollTop || 0;
    toolbarRevealTimer = null;
  }, TOOLBAR_REVEAL_DELAY_MS);
}

function revealFormattingToolbar() {
  toolbarDucked.value = false;
  toolbarScrollAnchor = toolbarScrollContainer?.scrollTop || 0;
  if (toolbarRevealTimer) window.clearTimeout(toolbarRevealTimer);
  toolbarRevealTimer = null;
}

function restoreWorkspaceScroll(top) {
  const scrollElement = toolbarScrollContainer
    || surfaceEl.value?.closest('.note-workspace-editor__scroll');
  if (!scrollElement) return;
  const targetTop = Math.max(0, Number(top) || 0);
  restoringWorkspaceScroll = true;
  toolbarDucked.value = false;
  scrollElement.scrollTop = targetTop;
  toolbarScrollAnchor = scrollElement.scrollTop;
  if (toolbarScrollRestoreFrame) window.cancelAnimationFrame(toolbarScrollRestoreFrame);
  toolbarScrollRestoreFrame = window.requestAnimationFrame(() => {
    // Chromium kann die Auswahl beim Einblenden eines Overlays erst im
    // nächsten Frame nachführen. Ein zweites Setzen hält dabei die zuvor
    // gewählte Schreibposition stabil.
    scrollElement.scrollTop = targetTop;
    toolbarScrollAnchor = scrollElement.scrollTop;
    restoringWorkspaceScroll = false;
    toolbarScrollRestoreFrame = null;
  });
}

// Externe modelValue-Änderung (z. B. Reset) übernehmen, ohne Tipp-Feedback-Loop.
watch(() => props.modelValue, (next) => {
  const ed = editor.value;
  if (!ed) return;
  const current = JSON.stringify(ed.getJSON());
  if (JSON.stringify(next || '') === current) return;
  // Ein verzögertes KI-Ergebnis darf niemals in eine inzwischen ausgewählte
  // andere Notiz geschrieben werden.
  if (aiPrompt.open) closeAIPrompt();
  closeLinkEditor();
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

function updateWordCount(ed) {
  // TipTap betrachtet auch mehrere leere Absätze als `isEmpty`. Der visuelle
  // Schreibhilfe-Zustand gilt jedoch nur für das unberührte Startdokument.
  editorEmpty.value = isPristineEmptyDocument(ed);
  if (editorEmpty.value) scheduleEmptyHintPosition();
  else emptyHintPositioned.value = false;
  words.value = countWords(ed?.getText());
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
  if (!ed) return;
  if (position === 'start' || position === 'end') {
    ed.chain().focus(position).run();
    return;
  }
  ed.chain().focus().run();
}

function focusEditorEndFromWhitespace(event) {
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
  ed.chain().focus('end').run();
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

function clearNoteSearch() {
  setNoteSearch(editor.value, '', -1);
  emitNoteSearchState();
}

defineExpose({
  clearNoteSearch,
  focusTitle,
  focusBody,
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
    blockquote: () => chain.toggleBlockquote(),
    codeBlock: () => chain.toggleCodeBlock(),
  };
  commands[action]?.().run();
}

function positionLinkEditor() {
  const ed = editor.value;
  const surface = surfaceEl.value;
  if (!ed || !surface) return;
  const from = Math.min(linkEditor.range.from, ed.state.doc.content.size);
  const to = Math.min(Math.max(from, linkEditor.range.to), ed.state.doc.content.size);
  const rect = posToDOMRect(ed.view, from, to);
  const box = surface.getBoundingClientRect();
  linkEditor.style = {
    left: `${clampMenuLeft(rect.left - box.left, box.width, 360)}px`,
    top: `${rect.bottom - box.top + 4}px`,
  };
}

function openLinkEditor(options = null) {
  const ed = editor.value;
  if (!ed) return;
  const explicitRange = Number.isInteger(options?.from) && Number.isInteger(options?.to);
  if (!explicitRange && ed.isActive('link') && ed.state.selection.empty) {
    ed.chain().focus().extendMarkRange('link').run();
  }
  const selection = explicitRange
    ? { from: options.from, to: options.to }
    : { from: ed.state.selection.from, to: ed.state.selection.to };
  const href = String(options?.href || ed.getAttributes('link').href || '');

  linkEditor.range = selection;
  linkEditor.href = href;
  linkEditor.existing = Boolean(href);
  linkEditor.copied = false;
  linkEditor.error = '';
  positionLinkEditor();
  linkEditor.open = true;
  tableMenu.open = false;
  slash.open = false;
  picker.open = false;
  bubble.show = false;
  closeAIPrompt();
  nextTick(() => {
    linkInputEl.value?.focus();
    linkInputEl.value?.select();
  });
}

function closeLinkEditor(restoreFocus = false) {
  linkEditor.open = false;
  linkEditor.error = '';
  linkEditor.copied = false;
  if (restoreFocus) nextTick(() => editor.value?.chain().focus().run());
}

function applyLink() {
  const ed = editor.value;
  const normalizedHref = normalizeNoteHref(linkEditor.href);
  if (!ed || !normalizedHref) {
    linkEditor.error = 'Bitte eine gültige Web- oder E-Mail-Adresse eingeben.';
    return;
  }
  const from = Math.min(linkEditor.range.from, ed.state.doc.content.size);
  const to = Math.min(Math.max(from, linkEditor.range.to), ed.state.doc.content.size);
  const attrs = { href: normalizedHref, target: '_blank', rel: 'noopener noreferrer' };
  linkEditor.open = false;

  if (from === to) {
    const label = noteHrefLabel(linkEditor.href, normalizedHref);
    ed.chain()
      .focus()
      .setTextSelection(from)
      // Ein unformatiertes Leerzeichen beendet den Link sauber. Dadurch wird
      // nach dem Einfügen nicht versehentlich im Link weitergeschrieben.
      .insertContent([
        { type: 'text', text: label, marks: [{ type: 'link', attrs }] },
        { type: 'text', text: ' ' },
      ])
      .run();
    return;
  }
  ed.chain().focus().setTextSelection({ from, to }).setLink(attrs).run();
}

function removeLink() {
  const ed = editor.value;
  if (!ed) return;
  const from = Math.min(linkEditor.range.from, ed.state.doc.content.size);
  const to = Math.min(Math.max(from, linkEditor.range.to), ed.state.doc.content.size);
  linkEditor.open = false;
  ed.chain().focus().setTextSelection({ from, to }).unsetLink().run();
}

function openLinkTarget() {
  const href = normalizeNoteHref(linkEditor.href);
  if (!href) {
    linkEditor.error = 'Dieser Link ist nicht gültig.';
    return;
  }
  if (href.startsWith('mailto:')) window.location.href = href;
  else window.open(href, '_blank', 'noopener,noreferrer');
}

async function copyLinkTarget() {
  const href = normalizeNoteHref(linkEditor.href);
  if (!href) {
    linkEditor.error = 'Dieser Link ist nicht gültig.';
    return;
  }
  try {
    await navigator.clipboard.writeText(href);
    linkEditor.copied = true;
    if (linkCopiedTimer) window.clearTimeout(linkCopiedTimer);
    linkCopiedTimer = window.setTimeout(() => {
      linkEditor.copied = false;
      linkCopiedTimer = null;
    }, 1400);
  } catch {
    linkEditor.error = 'Der Link konnte nicht kopiert werden.';
  }
}

function handleEditorPaste(event) {
  const ed = editor.value;
  if (!ed || ed.state.selection.empty) return false;
  const raw = event.clipboardData?.getData('text/plain')?.trim() || '';
  const href = normalizeNoteHref(raw);
  if (!href) return false;
  event.preventDefault();
  ed.chain()
    .focus()
    .setLink({ href, target: '_blank', rel: 'noopener noreferrer' })
    .run();
  return true;
}

function handleEditorLinkClick(view, event) {
  const target = event.target instanceof Element ? event.target.closest('a[href]') : null;
  if (!target) return false;
  event.preventDefault();
  try {
    const from = view.posAtDOM(target, 0);
    const to = view.posAtDOM(target, target.childNodes.length);
    editor.value?.commands.setTextSelection({ from, to });
    nextTick(() => openLinkEditor({ from, to, href: target.getAttribute('href') || '' }));
    return true;
  } catch {
    return false;
  }
}

function positionTableMenu() {
  const ed = editor.value;
  const surface = surfaceEl.value;
  if (!ed || !surface) return;
  const pos = Math.min(tableMenu.anchorPos ?? ed.state.selection.from, ed.state.doc.content.size);
  const rect = posToDOMRect(ed.view, pos, pos);
  const box = surface.getBoundingClientRect();
  tableMenu.style = {
    left: `${clampMenuLeft(rect.left - box.left, box.width, 286)}px`,
    top: `${rect.bottom - box.top + 4}px`,
  };
}

function tableWrapperAtSelection() {
  const ed = editor.value;
  if (!ed?.isActive('table')) return null;
  const domAtSelection = ed.view.domAtPos(ed.state.selection.from)?.node;
  const element = domAtSelection instanceof Element
    ? domAtSelection
    : domAtSelection?.parentElement;
  return element?.closest('.tableWrapper') || null;
}

function positionTableHandle(wrapper) {
  const surface = surfaceEl.value;
  if (!surface || !(wrapper instanceof Element)) return;
  const surfaceRect = surface.getBoundingClientRect();
  const tableRect = wrapper.getBoundingClientRect();
  const outsideLeft = tableRect.left - surfaceRect.left - 30;
  tableHandle.style = {
    left: `${outsideLeft >= 2 ? outsideLeft : tableRect.left - surfaceRect.left + 6}px`,
    top: `${tableRect.top - surfaceRect.top + 7}px`,
  };
  tableHandle.visible = true;
  activeTableWrapper = wrapper;
}

function refreshTableHandle() {
  const wrapper = hoveredTableWrapper || tableWrapperAtSelection();
  if (!wrapper || !surfaceEl.value?.contains(wrapper)) {
    tableHandle.visible = false;
    activeTableWrapper = null;
    return;
  }
  positionTableHandle(wrapper);
}

function trackTableHandle(event) {
  const target = event.target;
  if (!(target instanceof Element) || target.closest('.pm-table-handle, .pm-table-menu')) return;
  hoveredTableWrapper = target.closest('.tableWrapper');
  refreshTableHandle();
}

function clearHoveredTable() {
  hoveredTableWrapper = null;
  refreshTableHandle();
}

function openTableMenuFromHandle() {
  const ed = editor.value;
  const surface = surfaceEl.value;
  const wrapper = activeTableWrapper;
  if (!ed || !surface || !(wrapper instanceof Element)) return;

  const cellContent = wrapper.querySelector('th p, td p, th, td');
  if (cellContent) {
    const pos = ed.view.posAtDOM(cellContent, 0);
    ed.chain().focus().setTextSelection(pos).run();
  }

  const surfaceRect = surface.getBoundingClientRect();
  const tableRect = wrapper.getBoundingClientRect();
  tableMenu.mode = 'edit';
  tableMenu.anchorPos = ed.state.selection.from;
  tableMenu.style = {
    left: `${clampMenuLeft(tableRect.left - surfaceRect.left + 4, surfaceRect.width, 286)}px`,
    top: `${tableRect.top - surfaceRect.top + 36}px`,
  };
  tableMenu.open = true;
  slash.open = false;
  picker.open = false;
  bubble.show = false;
  closeLinkEditor();
  closeAIPrompt();
}

function openTableMenu(requestedMode = null) {
  const ed = editor.value;
  if (!ed) return;
  const explicitMode = requestedMode === 'insert' || requestedMode === 'edit' ? requestedMode : null;
  tableMenu.mode = explicitMode || (ed.isActive('table') ? 'edit' : 'insert');
  tableMenu.rows = 3;
  tableMenu.cols = 3;
  tableMenu.withHeaderRow = true;
  tableMenu.withHeaderColumn = false;
  tableMenu.anchorPos = ed.state.selection.from;
  positionTableMenu();
  tableMenu.open = true;
  slash.open = false;
  picker.open = false;
  bubble.show = false;
  closeLinkEditor();
  closeAIPrompt();
}

function selectTableSize(rows, cols) {
  tableMenu.rows = Math.min(TABLE_PICKER_SIZE, Math.max(1, Number(rows) || 1));
  tableMenu.cols = Math.min(TABLE_PICKER_SIZE, Math.max(1, Number(cols) || 1));
}

function selectTableHeaderMode(mode) {
  tableMenu.withHeaderRow = mode !== 'column';
  tableMenu.withHeaderColumn = mode === 'column';
}

function insertTable(rows = tableMenu.rows, cols = tableMenu.cols) {
  const ed = editor.value;
  if (!ed) return;
  const anchorPos = Math.min(tableMenu.anchorPos ?? ed.state.selection.from, ed.state.doc.content.size);
  tableMenu.open = false;
  const chain = ed.chain()
    .focus()
    .setTextSelection(anchorPos)
    .insertTable({
      rows: Math.max(1, Number(rows) || 1),
      cols: Math.max(1, Number(cols) || 1),
      withHeaderRow: tableMenu.withHeaderRow,
    });
  if (tableMenu.withHeaderColumn) chain.toggleHeaderColumn();
  chain.scrollIntoView().run();
}

function runTableCommand(action) {
  const ed = editor.value;
  if (!ed || !ed.isActive('table')) return;
  const chain = ed.chain().focus();
  const commands = {
    addRowAfter: () => chain.addRowAfter(),
    addColumnAfter: () => chain.addColumnAfter(),
    toggleHeaderRow: () => chain.toggleHeaderRow(),
    toggleHeaderColumn: () => chain.toggleHeaderColumn(),
    deleteRow: () => chain.deleteRow(),
    deleteColumn: () => chain.deleteColumn(),
    deleteTable: () => chain.deleteTable(),
  };
  tableMenu.open = false;
  commands[action]?.().run();
}

/* ── Status-Anzeige ──────────────────────────────────────────────────────── */
const saveLabel = computed(() => (
  { saving: 'Speichert …', saved: 'Gespeichert', idle: 'Bereit' }[props.status] || 'Bereit'
));

/* ── Bubble-Menü (Auswahl-Formatierung) ─────────────────────────────────────── */
const bubble = reactive({ show: false, style: {} });
const BUBBLE_VIEWPORT_MARGIN = 8;
const BUBBLE_BUTTON_WIDTH = 32;
const BUBBLE_AI_BUTTON_WIDTH = 36;
const BUBBLE_GAP = 2;
const BUBBLE_SHELL_WIDTH = 10;

const bubbleButtons = computed(() => {
  const ed = editor.value;
  if (!ed) return [];
  const mk = (key, label, glyph, isActive, run) => ({
    key, label, glyph,
    active: () => isActive(ed),
    run: () => { run(ed.chain().focus()).run(); refreshBubble(); },
  });
  return [
    mk('bold', 'Fett', '<b>B</b>', e => e.isActive('bold'), c => c.toggleBold()),
    mk('italic', 'Kursiv', '<i>I</i>', e => e.isActive('italic'), c => c.toggleItalic()),
    mk('underline', 'Unterstrichen', '<u>U</u>', e => e.isActive('underline'), c => c.toggleUnderline()),
    mk('strike', 'Durchgestrichen', '<s>S</s>', e => e.isActive('strike'), c => c.toggleStrike()),
    mk('code', 'Code', '<code>&lt;&gt;</code>', e => e.isActive('code'), c => c.toggleCode()),
    {
      key: 'link',
      label: 'Hyperlink',
      glyph: '&#8599;',
      active: () => ed.isActive('link'),
      run: () => openLinkEditor(),
    },
    mk('h2', 'Überschrift 2', 'H2', e => e.isActive('heading', { level: 2 }), c => c.toggleHeading({ level: 2 })),
    mk('h3', 'Überschrift 3', 'H3', e => e.isActive('heading', { level: 3 }), c => c.toggleHeading({ level: 3 })),
    mk('h4', 'Überschrift 4', 'H4', e => e.isActive('heading', { level: 4 }), c => c.toggleHeading({ level: 4 })),
    mk('quote', 'Zitat', '&#10077;', e => e.isActive('blockquote'), c => c.toggleBlockquote()),
    ...(props.aiAvailable ? [{
      key: 'ai-selection',
      label: 'Auswahl mit KI bearbeiten',
      glyph: '&#10022;',
      ai: true,
      active: () => false,
      run: () => openAIPrompt(),
    }] : []),
  ];
});

function refreshBubble() {
  const ed = editor.value;
  const surface = surfaceEl.value;
  if (!ed || !surface) { bubble.show = false; return; }
  const { state, view } = ed;
  const { from, to, empty } = state.selection;
  const isText = state.selection.constructor?.name === 'TextSelection'
    || Object.prototype.hasOwnProperty.call(state.selection, '$cursor');
  if (empty || !isText || !ed.isEditable || slash.open || picker.open || tableMenu.open || linkEditor.open) {
    bubble.show = false;
    return;
  }

  const rect = posToDOMRect(view, from, to);
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
  bubble.style = {
    left: `${clampCenterToViewport(estimatedWidth)}px`,
    top: `${rect.top}px`,
    transform: 'translate(-50%, calc(-100% - 8px))',
  };
  bubble.show = true;
  nextTick(() => {
    const measuredWidth = bubbleEl.value?.offsetWidth;
    if (!bubble.show || !measuredWidth) return;
    bubble.style = {
      ...bubble.style,
      left: `${clampCenterToViewport(measuredWidth)}px`,
    };
  });
}

/* ── Slash-Menü ──────────────────────────────────────────────────────────── */
const SLASH_COMMANDS = [
  // PaperMind-eigene Bausteine.
  { key: 'beleg', group: 'papermind', chip: '▢', label: 'Beleg verknüpfen', desc: 'Dokument-Chip einfügen', terms: ['beleg', 'dokument', 'chip', 'verknüpfen'], kind: 'pick-doc-chip' },
  { key: 'zitat', group: 'papermind', chip: '❝', label: 'Beleg-Zitat', desc: 'OCR-Passage übernehmen', terms: ['zitat', 'beleg', 'ocr', 'markierung'], kind: 'pick-doc-quote' },
  { key: 'ki-schreiben', group: 'papermind', chip: '✦', label: 'Mit KI schreiben', desc: 'Text generieren und einfügen', terms: ['ki', 'ai', 'prompt', 'schreiben', 'text', 'generieren'], kind: 'generate-ai' },
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
  { key: 'quote', group: 'blocks', chip: '❝', label: 'Zitat', desc: 'Zitatblock', terms: ['zitat', 'quote'], action: c => c.toggleBlockquote() },
  { key: 'code', group: 'blocks', chip: '</>', label: 'Code-Block', desc: 'Monospace', terms: ['code', 'block'], action: c => c.toggleCodeBlock() },
  { key: 'hr', group: 'blocks', chip: '―', label: 'Trennlinie', desc: 'Horizontale Linie', terms: ['trennlinie', 'linie', 'rule'], action: c => c.setHorizontalRule() },
];

const SLASH_GROUPS = [
  { key: 'callouts', label: 'Hinweisblöcke' },
  { key: 'headings', label: 'Überschriften' },
  { key: 'inline', label: 'Text & Links' },
  { key: 'blocks', label: 'Listen & Blöcke' },
  { key: 'papermind', label: 'PaperMind' },
];

const slash = reactive({
  open: false,
  query: '',
  from: null,
  index: 0,
  style: {},
  selectionStyle: {},
  selectionVisible: false,
});

// „Real-Modus": echte Datenquelle vorhanden (Workspace) → Mock-only-Befehle
// ausblenden. Die echte Textgenerierung bleibt in beiden Varianten verfügbar.
const realMode = computed(() => Array.isArray(props.documentItems));
const availableSlashCommands = computed(() =>
  SLASH_COMMANDS.filter((command) => {
    if (realMode.value && command.kind === 'pick-doc-quote') return false;
    if (!props.aiAvailable && command.kind === 'generate-ai') return false;
    return true;
  })
);

const slashResults = computed(() => {
  const base = availableSlashCommands.value;
  const q = slash.query.trim().toLowerCase();
  if (!q) return base;
  return base.filter(c =>
    c.label.toLowerCase().includes(q) || c.terms.some(t => t.includes(q))
  );
});

const slashGroups = computed(() => {
  let flatIndex = 0;
  return SLASH_GROUPS.map((group) => {
    const items = slashResults.value
      .filter((command) => command.group === group.key)
      .map((command) => ({ command, index: flatIndex++ }));
    return { ...group, items };
  }).filter((group) => group.items.length);
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

  // Nur in Text-Blöcken, nicht in Code-Blöcken.
  if (!$from.parent.isTextblock || $from.parent.type.name === 'codeBlock') { slash.open = false; return; }

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
  if (kind === 'link-editor') { openLinkEditor(); return; }
  if (kind === 'generate-ai') { openAIPrompt(); return; }
  if (kind === 'pick-doc-chip') {
    openPicker('document', docPickerItems(), (item) =>
      ed.chain().focus().insertDocumentChip({ docId: item.id, title: item.label }).run());
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
    openPicker('target', linkTargetItems(), (item) =>
      ed.chain().focus().insertWikiLink({ targetType: item.type, targetId: item.id, label: item.label }).run());
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

/* ── KI-Schreibassistenz ─────────────────────────────────────────────────── */
const AI_PROMPT_WIDTH = 390;
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
  mode: 'context',
  instruction: '',
  generatedInstruction: '',
  preview: '',
  error: '',
  loading: false,
  provider: '',
  model: '',
  anchorPos: null,
  selectionFrom: null,
  selectionTo: null,
  selectedText: '',
  style: {},
});
const aiSelectionTooLong = computed(() => (
  aiPrompt.mode === 'selection' && aiPrompt.selectedText.length > 8000
));
const aiContextLabel = computed(() => (
  aiPrompt.mode === 'selection'
    ? `Kontext: nur Auswahl · ${aiPrompt.selectedText.length.toLocaleString('de-DE')} Zeichen`
    : 'Kontext: Notiztext bis zum Cursor'
));

function providerLabel(provider) {
  return { ollama: 'Lokal', openai: 'OpenAI', anthropic: 'Claude' }[provider] || 'KI';
}

function positionAIPrompt() {
  const ed = editor.value, surface = surfaceEl.value;
  if (!ed || !surface) return;
  const pos = Math.min(aiPrompt.anchorPos ?? ed.state.selection.from, ed.state.doc.content.size);
  const rect = posToDOMRect(ed.view, pos, pos);
  const box = surface.getBoundingClientRect();
  aiPrompt.style = {
    left: `${clampMenuLeft(rect.left - box.left, box.width, AI_PROMPT_WIDTH)}px`,
    top: `${rect.bottom - box.top + 4}px`,
  };
}

function openAIPrompt() {
  const ed = editor.value;
  if (!ed) return;
  const { from, to, empty } = ed.state.selection;
  const selectedText = empty ? '' : ed.state.doc.textBetween(from, to, '\n', '\n').trim();
  aiPrompt.mode = selectedText ? 'selection' : 'context';
  aiPrompt.anchorPos = selectedText ? to : from;
  aiPrompt.selectionFrom = selectedText ? from : null;
  aiPrompt.selectionTo = selectedText ? to : null;
  aiPrompt.selectedText = selectedText;
  aiPrompt.instruction = '';
  aiPrompt.generatedInstruction = '';
  aiPrompt.preview = '';
  aiPrompt.error = selectedText.length > 8000
    ? 'Die Auswahl ist zu lang. Bitte höchstens 8.000 Zeichen markieren.'
    : '';
  aiPrompt.provider = '';
  aiPrompt.model = '';
  aiPrompt.open = true;
  positionAIPrompt();
  tableMenu.open = false;
  picker.open = false;
  bubble.show = false;
  closeLinkEditor();
  nextTick(() => aiPromptInputEl.value?.focus());
}

function closeAIPrompt() {
  aiGenerationController?.abort();
  aiGenerationController = null;
  aiPrompt.open = false;
  aiPrompt.loading = false;
  aiPrompt.preview = '';
  aiPrompt.error = '';
  aiPrompt.generatedInstruction = '';
  aiPrompt.selectedText = '';
  aiPrompt.selectionFrom = null;
  aiPrompt.selectionTo = null;
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
  return {
    text: aiPrompt.preview.trim(),
    prompt: aiPrompt.generatedInstruction || aiPrompt.instruction.trim(),
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

function applySelectionAIResult(action) {
  const ed = editor.value;
  if (!ed || aiPrompt.mode !== 'selection' || !aiPrompt.preview.trim()) return;
  if (!selectionSnapshotIsCurrent(ed)) {
    aiPrompt.error = 'Die Textauswahl hat sich geändert. Bitte schließen und erneut auswählen.';
    return;
  }

  const from = aiPrompt.selectionFrom;
  const to = aiPrompt.selectionTo;
  const attrs = aiBlockAttrs();
  const chain = ed.chain().focus();
  if (action === 'replace') {
    chain.insertContentAt({ from, to }, { type: 'aiBlock', attrs });
  } else {
    chain.setTextSelection(to).insertAiBlock(attrs);
  }
  chain.focus('end').scrollIntoView().run();
  emit('history-checkpoint', 'ai');
  closeAIPrompt();
}

async function generateAIText() {
  const ed = editor.value;
  const instruction = aiPrompt.instruction.trim();
  if (!ed || !instruction || aiPrompt.loading || aiSelectionTooLong.value) return;

  aiPrompt.loading = true;
  aiPrompt.generatedInstruction = instruction;
  aiPrompt.preview = '';
  aiPrompt.error = '';
  aiPrompt.provider = '';
  aiPrompt.model = '';
  aiGenerationController = new AbortController();

  try {
    await streamNoteText({
      instruction,
      note_context: aiPrompt.mode === 'selection' ? '' : noteContextBeforeAnchor(ed),
      selected_text: aiPrompt.mode === 'selection' ? aiPrompt.selectedText : '',
      document_context: '',
    }, {
      signal: aiGenerationController.signal,
      onEvent: (event) => {
        if (event.type === 'meta') {
          aiPrompt.provider = event.provider || '';
          aiPrompt.model = event.model || '';
        } else if (event.type === 'delta') {
          aiPrompt.preview += event.text || '';
        }
      },
    });

    const text = aiPrompt.preview.trim();
    if (!text) throw new Error('Das Modell hat keinen Text erzeugt.');
    if (aiPrompt.mode === 'selection') {
      if (!selectionSnapshotIsCurrent(ed)) {
        throw new Error('Die Textauswahl hat sich geändert. Bitte schließen und erneut auswählen.');
      }
      return;
    }
    const insertionPos = Math.min(aiPrompt.anchorPos ?? ed.state.selection.from, ed.state.doc.content.size);
    ed.chain()
      .focus()
      .setTextSelection(insertionPos)
      .insertAiBlock({ ...aiBlockAttrs() })
      .focus('end')
      .scrollIntoView()
      .run();
    emit('history-checkpoint', 'ai');
    aiPrompt.open = false;
  } catch (error) {
    if (error?.name !== 'AbortError' && aiPrompt.open) {
      aiPrompt.error = error?.message || 'Text konnte nicht generiert werden.';
    }
  } finally {
    aiPrompt.loading = false;
    aiGenerationController = null;
  }
}

/* ── Ziel-/Beleg-Picker (für /beleg, /zitat, /verweis und den [[-Trigger) ───── */
const picker = reactive({ open: false, mode: 'document', items: [], index: 0, style: {}, live: false, from: null, query: '', onPick: null });

const filteredPicker = computed(() => {
  const q = picker.query.trim().toLowerCase();
  if (!q) return picker.items;
  return picker.items.filter(it =>
    it.label.toLowerCase().includes(q) || (it.hint || '').toLowerCase().includes(q));
});

function pickerHint() { return picker.mode === 'target' ? 'Verweisen auf' : 'Beleg wählen'; }
function pickerChip(it) { return targetGlyph(it.type); }

function positionPicker() {
  const ed = editor.value, surface = surfaceEl.value;
  if (!ed || !surface) return;
  const pos = ed.state.selection.from;
  const rect = posToDOMRect(ed.view, pos, pos);
  const box = surface.getBoundingClientRect();
  picker.style = {
    left: `${clampMenuLeft(rect.left - box.left, box.width)}px`,
    top: `${rect.bottom - box.top + 4}px`,
  };
}

function openPicker(mode, items, onPick) {
  picker.mode = mode; picker.items = items; picker.onPick = onPick;
  picker.live = false; picker.from = null; picker.query = ''; picker.index = 0;
  positionPicker(); picker.open = true;
  slash.open = false; tableMenu.open = false; bubble.show = false;
  closeLinkEditor();
}

function pickItem(item) {
  if (!item) return;
  const ed = editor.value;
  const onPick = picker.onPick;
  // Live-Picker ([[): den getippten „[[query"-Text vor dem Einfügen entfernen.
  if (picker.live && picker.from != null && ed) {
    const to = ed.state.selection.from;
    ed.chain().focus().deleteRange({ from: picker.from, to }).run();
  }
  picker.open = false;
  onPick?.(item);
}

// [[-Trigger: erkennt „[[query" am Cursor und öffnet den Ziel-Picker live.
function refreshWikiLink() {
  const ed = editor.value, surface = surfaceEl.value;
  if (!ed || !surface) return;
  const { $from, empty } = ed.state.selection;
  const closeLive = () => { if (picker.live) picker.open = false; };
  if (!empty) { closeLive(); return; }
  if (!$from.parent.isTextblock || $from.parent.type.name === 'codeBlock') { closeLive(); return; }

  const before = $from.parent.textBetween(0, $from.parentOffset, '￼', '￼');
  const m = /\[\[([^[\]]*)$/.exec(before);
  if (!m) { closeLive(); return; }

  const query = m[1];
  picker.mode = 'target';
  picker.items = linkTargetItems();
  picker.live = true;
  picker.from = ed.state.selection.from - (query.length + 2);
  picker.query = query;
  picker.onPick = (item) =>
    ed.chain().focus().insertWikiLink({ targetType: item.type, targetId: item.id, label: item.label }).run();
  if (!picker.open) picker.index = 0;
  positionPicker();
  picker.open = true;
  slash.open = false;
  closeLinkEditor();
}

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

  if (tableMenu.open) {
    if (event.key === 'Escape') { tableMenu.open = false; return true; }
    if (tableMenu.mode === 'insert') {
      if (event.key === 'ArrowRight') { selectTableSize(tableMenu.rows, tableMenu.cols + 1); return true; }
      if (event.key === 'ArrowLeft') { selectTableSize(tableMenu.rows, tableMenu.cols - 1); return true; }
      if (event.key === 'ArrowDown') { selectTableSize(tableMenu.rows + 1, tableMenu.cols); return true; }
      if (event.key === 'ArrowUp') { selectTableSize(tableMenu.rows - 1, tableMenu.cols); return true; }
      if (event.key === 'Enter') { insertTable(); return true; }
    }
  }

  // Picker (Beleg-/Ziel-Auswahl) hat Vorrang.
  if (picker.open) {
    const items = filteredPicker.value;
    if (items.length) {
      const n = items.length;
      if (event.key === 'ArrowDown') { picker.index = (picker.index + 1) % n; return true; }
      if (event.key === 'ArrowUp') { picker.index = (picker.index - 1 + n) % n; return true; }
      if (event.key === 'Enter' || event.key === 'Tab') { pickItem(items[picker.index]); return true; }
    }
    if (event.key === 'Escape') { picker.open = false; return true; }
    // Live-Picker: Tippen/Backspace fließt in den [[…]]-Text (Query wächst/schrumpft).
    return false;
  }

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
watch(filteredPicker, (r) => { if (picker.index >= r.length) picker.index = 0; });
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
     - block-gap: mehr Luft vor/nach Strukturelementen (Listen, Zitate, Codeblock),
       damit diese sich sichtbar vom Fließtext absetzen. */
  --note-editor-paragraph-gap: 0.5em;
  --note-editor-block-gap: 0.95em;
}

.note-editor--font-serif {
  --note-editor-font-family: Georgia, "Times New Roman", serif;
}

.note-editor--font-mono {
  --note-editor-font-family: ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, monospace;
}

.note-editor--spacing-compact {
  --note-editor-paragraph-gap: 0.3em;
  --note-editor-block-gap: 0.6em;
}

.note-editor--spacing-spacious {
  --note-editor-paragraph-gap: 0.75em;
  --note-editor-block-gap: 1.3em;
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

.note-editor__toolbar {
  position: sticky;
  top: 12px;
  z-index: 12;
  display: flex;
  box-sizing: border-box;
  width: max-content;
  max-width: calc(100% - 32px);
  min-height: 44px;
  flex: none;
  align-self: center;
  align-items: center;
  gap: 6px;
  margin: 12px auto 0;
  padding: 5px 7px;
  overflow-x: auto;
  overflow-y: hidden;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 88%, transparent);
  border-radius: 12px;
  /* Deckende Fläche statt backdrop-filter: Ein sticky-Element mit
     backdrop-filter über dem scrollenden Editor löst in Chromium
     Schreibmarken-Geister aus (die echte Caret-Fläche wird beim Scrollen
     nicht invalidiert, es bleiben eingefrorene Caret-Kopien stehen). */
  background: var(--pm-app-surface-raised, #fff);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  scrollbar-color: color-mix(in srgb, var(--pm-muted, #535e62) 35%, transparent) transparent;
  scrollbar-width: thin;
  transition:
    background-color 220ms ease,
    border-color 220ms ease,
    box-shadow 220ms ease;
}

.note-editor__toolbar.is-ducked {
  border-color: color-mix(in srgb, var(--pm-divider, #d8dfe1) 18%, transparent);
  /* Weiterhin deckend (siehe oben) – das „Ducken“ liest sich nun über
     Rahmen und Schatten, nicht mehr über Transparenz + Blur. */
  background: var(--pm-app-surface-raised, #fff);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.015);
}

.note-editor__toolbar.is-ducked:hover,
.note-editor__toolbar.is-ducked:focus-within {
  border-color: color-mix(in srgb, var(--pm-divider, #d8dfe1) 88%, transparent);
  background: var(--pm-app-surface-raised, #fff);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
}

.note-editor__toolbar-group {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 2px;
}

.note-editor__toolbar-divider {
  width: 1px;
  height: 24px;
  flex: none;
  margin: 0 2px;
  background: var(--pm-divider, #d8dfe1);
}

.note-editor__toolbar-btn {
  display: inline-grid;
  width: 32px;
  height: 32px;
  flex: none;
  place-items: center;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  font: inherit;
  font-size: 0.88rem;
  transition: background-color 120ms ease, color 120ms ease;
}

.note-editor__toolbar-btn--text {
  width: 40px;
  font-weight: 680;
}

.note-editor__toolbar-btn--wide {
  width: 48px;
  font-weight: 570;
}

.note-editor__toolbar-btn:hover {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 9%, transparent);
  color: var(--pm-text, #0e181b);
}

.note-editor__toolbar-btn.is-active {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 14%, transparent);
  color: var(--pm-accent-strong, #00555f);
}

.note-editor__toolbar-code {
  color: var(--pm-warning, #c88819);
  font-weight: 700;
}

.note-editor__toolbar-braces {
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.72rem;
  letter-spacing: -0.08em;
}

.note-editor--workspace .note-editor__surface {
  min-height: 420px;
  padding: 24px clamp(28px, 5vw, 58px) 88px;
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

.note-editor--workspace.is-centered .note-editor__writing {
  margin-inline: auto;
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
.note-editor :deep(.pm-content > *) {
  /* Browser-Margen würden zusätzlich zum konfigurierten Abstand wirken und
     einen einzelnen neuen Absatz wie zwei Zeilenumbrüche erscheinen lassen. */
  margin-block: 0;
}
.note-editor :deep(.pm-content > * + *) { margin-top: var(--note-editor-paragraph-gap); }
/* Strukturelemente heben sich stärker vom Fließtext ab: mehr Luft davor … */
.note-editor :deep(.pm-content > * + :is(ul, ol, blockquote, pre)) {
  margin-top: var(--note-editor-block-gap);
}
/* … und danach. */
.note-editor :deep(.pm-content > :is(ul, ol, blockquote, pre) + *) {
  margin-top: var(--note-editor-block-gap);
}
.note-editor :deep(.pm-content h1) {
  font-family: inherit; font-weight: 600;
  font-size: 1.55rem; line-height: 1.2; letter-spacing: -0.01em; margin-top: 1.4em;
}
.note-editor :deep(.pm-content h2) {
  font-family: inherit; font-weight: 600;
  font-size: 1.28rem; line-height: 1.25; margin-top: 1.3em;
}
.note-editor :deep(.pm-content h3) { font-weight: 600; font-size: 1.08rem; margin-top: 1.2em; }
.note-editor :deep(.pm-content h4) { font-weight: 600; font-size: 1rem; margin-top: 1.1em; }
.note-editor :deep(.pm-content > h2:first-child),
.note-editor :deep(.pm-content > h3:first-child),
.note-editor :deep(.pm-content > h4:first-child) {
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
  border: 0; height: 1px; background: var(--pm-divider, #d8dfe1); margin: 1.4em 0;
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
.note-editor :deep(.pm-content ul[data-type="taskList"] li > label) { margin-top: 0.28em; }
.note-editor :deep(.pm-content ul[data-type="taskList"] input) { accent-color: var(--pm-accent, #006b75); }

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

.pm-table-handle {
  position: absolute;
  z-index: 9;
  display: grid;
  width: 26px;
  height: 30px;
  place-items: center;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 88%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--pm-app-surface-raised, #fff) 94%, transparent);
  box-shadow: 0 5px 14px color-mix(in srgb, var(--pm-text, #0e181b) 9%, transparent);
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  opacity: 0.82;
  transform-origin: center;
  animation: pm-table-handle-in 150ms cubic-bezier(0.16, 1, 0.3, 1) both;
  transition: opacity 130ms ease, color 130ms ease, background-color 130ms ease, transform 130ms ease;
}

.pm-table-handle:hover,
.pm-table-handle:focus-visible,
.pm-table-handle.is-open {
  outline: none;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 10%, var(--pm-app-surface-raised, #fff));
  color: var(--pm-accent-strong, #00555f);
  opacity: 1;
  transform: scale(1.04);
}

@keyframes pm-table-handle-in {
  from { opacity: 0; transform: translateX(4px) scale(0.9); }
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
.pm-float {
  position: absolute; z-index: 30;
  background: var(--pm-app-surface-raised, #fff);
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 12px;
  box-shadow: var(--pm-shadow, 0 10px 30px rgba(15, 23, 42, 0.14));
}

.pm-bubble {
  position: fixed;
  z-index: 80;
  display: flex;
  max-width: calc(100vw - 16px);
  padding: 4px;
  gap: 2px;
}
.pm-bubble__btn {
  border: 0; background: transparent; cursor: pointer;
  width: 32px; height: 32px; border-radius: 8px;
  display: grid; place-items: center;
  color: var(--pm-text, #0e181b); font-size: 0.95rem;
  transition: background 120ms ease, color 120ms ease;
}
.pm-bubble__btn:hover { background: rgba(var(--v-theme-primary, 0 107 117), 0.1); }
.pm-bubble__btn.is-active { background: var(--pm-accent, #006b75); color: var(--pm-accent-contrast, #fff); }
.pm-bubble__btn.is-ai {
  width: 36px;
  margin-left: 3px;
  border-left: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 0 8px 8px 0;
  color: var(--pm-accent-strong, #00555f);
}
.pm-bubble__glyph code { font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; }

.pm-link-editor {
  box-sizing: border-box;
  width: 360px;
  max-width: calc(100% - 16px);
  padding: 10px;
  color: var(--pm-text, #0e181b);
}

.pm-link-editor__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 1px 2px 8px;
  color: var(--pm-muted, #535e62);
  font-size: 0.76rem;
  font-weight: 650;
  letter-spacing: 0.02em;
}

.pm-link-editor__head > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.pm-link-editor__head kbd {
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 5px;
  background: color-mix(in srgb, var(--pm-viewer-surface, #eef2f4) 72%, transparent);
  padding: 1px 5px;
  color: var(--pm-muted, #535e62);
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.66rem;
  font-weight: 500;
}

.pm-link-editor__input-row {
  display: flex;
  align-items: stretch;
  gap: 6px;
}

.pm-link-editor__input-row input {
  min-width: 0;
  height: 38px;
  flex: 1 1 auto;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 8px;
  outline: none;
  background: var(--pm-content-surface, #fff);
  padding: 0 10px;
  color: var(--pm-text, #0e181b);
  font: inherit;
  font-size: 0.86rem;
  transition: border-color 120ms ease, box-shadow 120ms ease;
}

.pm-link-editor__input-row input::placeholder { color: var(--pm-muted, #8a969b); opacity: 0.72; }
.pm-link-editor__input-row input:focus {
  border-color: var(--pm-accent, #006b75);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--pm-accent, #006b75) 13%, transparent);
}
.pm-link-editor__input-row input[aria-invalid="true"] { border-color: var(--pm-danger, #b42318); }

.pm-link-editor__save {
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  border: 0;
  border-radius: 8px;
  background: var(--pm-accent, #006b75);
  color: var(--pm-accent-contrast, #fff);
  cursor: pointer;
  display: grid;
  place-items: center;
}

.pm-link-editor__save:hover { filter: brightness(1.07); }
.pm-link-editor__error {
  padding: 7px 2px 0;
  color: var(--pm-danger, #b42318);
  font-size: 0.74rem;
}

.pm-link-editor__actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--pm-divider, #d8dfe1);
}

.pm-link-editor__actions button {
  min-width: 0;
  height: 32px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font: inherit;
  font-size: 0.73rem;
}

.pm-link-editor__actions button:hover {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 9%, transparent);
  color: var(--pm-accent-strong, #00555f);
}

.pm-link-editor__actions button.is-danger:hover {
  background: color-mix(in srgb, var(--pm-danger, #b42318) 9%, transparent);
  color: var(--pm-danger, #b42318);
}

.pm-table-menu {
  width: 286px;
  padding: 10px;
}

.pm-table-menu__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 2px 3px 9px;
  color: var(--pm-text, #0e181b);
  font-size: 0.78rem;
  font-weight: 650;
}

.pm-table-menu__head strong {
  color: var(--pm-accent-strong, #00555f);
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.72rem;
}

.pm-table-menu__grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 5px;
}

.pm-table-menu__cell {
  aspect-ratio: 1.25;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 5px;
  outline: none;
  background: var(--pm-viewer-surface, #eef2f4);
  cursor: pointer;
  transition: background-color 100ms ease, border-color 100ms ease, transform 100ms ease;
}

.pm-table-menu__cell.is-selected {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 56%, var(--pm-divider, #d8dfe1));
  background: color-mix(in srgb, var(--pm-accent, #006b75) 18%, var(--pm-viewer-surface, #eef2f4));
}

.pm-table-menu__cell:hover,
.pm-table-menu__cell:focus-visible { transform: scale(1.06); }

.pm-table-menu__header-options {
  display: grid;
  gap: 3px;
  margin-top: 9px;
}

.pm-table-menu__header-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 7px 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  font: inherit;
  font-size: 0.73rem;
  text-align: left;
}

.pm-table-menu__header-toggle:hover,
.pm-table-menu__header-toggle.is-active {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 10%, transparent);
  color: var(--pm-accent-strong, #00555f);
}

.pm-table-menu__actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}

.pm-table-menu__actions button {
  display: grid;
  min-width: 0;
  grid-template-columns: 22px minmax(0, 1fr);
  align-items: center;
  gap: 6px;
  padding: 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-text, #0e181b);
  cursor: pointer;
  font: inherit;
  font-size: 0.7rem;
  text-align: left;
}

.pm-table-menu__actions button:hover,
.pm-table-menu__actions button:focus-visible {
  outline: none;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 9%, transparent);
  color: var(--pm-accent-strong, #00555f);
}

.pm-table-menu__actions button.is-danger:hover,
.pm-table-menu__actions button.is-danger:focus-visible {
  background: color-mix(in srgb, var(--pm-danger, #c84c4c) 10%, transparent);
  color: var(--pm-danger, #c84c4c);
}

.pm-table-menu__actions button.is-danger {
  grid-column: 1 / -1;
  margin-top: 2px;
  box-shadow: inset 0 1px 0 var(--pm-divider, #d8dfe1);
}

.pm-slash {
  width: 268px; padding: 6px; max-height: min(420px, calc(100vh - 140px)); overflow-y: auto;
  display: flex; flex-direction: column; gap: 1px;
}
.pm-slash--commands {
  position: fixed;
  overflow-anchor: none;
  transform-origin: 18px -5px;
  animation: pm-slash-open 235ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
.pm-slash__selection {
  position: absolute;
  z-index: 0;
  top: 0;
  left: 6px;
  right: 6px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 15%, transparent);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--pm-accent, #006b75) 7%, transparent);
  opacity: 0;
  pointer-events: none;
  transition:
    transform 165ms cubic-bezier(0.22, 1, 0.36, 1),
    height 140ms ease,
    opacity 90ms ease;
}
.pm-slash__selection.is-visible { opacity: 1; }
.pm-slash__hint,
.pm-slash__group { position: relative; z-index: 1; }
.pm-slash__hint {
  font-family: 'IBM Plex Mono', monospace; font-size: 10px;
  letter-spacing: 0.09em; text-transform: uppercase;
  color: var(--pm-muted, #535e62); padding: 6px 8px 4px;
}
.pm-slash__group + .pm-slash__group {
  margin-top: 5px;
  padding-top: 5px;
  border-top: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 72%, transparent);
}
.pm-slash__group-label {
  padding: 4px 8px 3px;
  color: var(--pm-muted, #535e62);
  font-family: 'IBM Plex Mono', monospace;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.pm-slash__item {
  border: 0; background: transparent; cursor: pointer; text-align: left;
  display: flex; align-items: center; gap: 10px;
  padding: 7px 8px; border-radius: 8px; width: 100%;
  transition: color 120ms ease;
}
.pm-slash__item.is-active { color: var(--pm-accent-strong, #00555f); }
.pm-slash__chip {
  flex: none; width: 30px; height: 30px; border-radius: 7px;
  display: grid; place-items: center;
  background: var(--pm-viewer-surface, #eef2f4);
  border: 1px solid var(--pm-divider, #d8dfe1);
  font-family: 'IBM Plex Mono', monospace; font-size: 12px;
  color: var(--pm-accent-strong, #00555f);
  transition:
    transform 165ms cubic-bezier(0.22, 1, 0.36, 1),
    border-color 140ms ease,
    background-color 140ms ease,
    box-shadow 140ms ease;
}
.pm-slash__item.is-active .pm-slash__chip {
  transform: scale(1.07);
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 38%, var(--pm-divider, #d8dfe1));
  background: color-mix(in srgb, var(--pm-accent, #006b75) 11%, var(--pm-viewer-surface, #eef2f4));
  box-shadow: 0 3px 10px color-mix(in srgb, var(--pm-accent, #006b75) 13%, transparent);
}
.pm-slash__text { display: flex; flex-direction: column; line-height: 1.2; }
.pm-slash__label { font-size: 0.9rem; color: var(--pm-text, #0e181b); }
.pm-slash__desc { font-size: 0.74rem; color: var(--pm-muted, #535e62); }

@keyframes pm-slash-open {
  0% {
    opacity: 0;
    transform: translateY(-10px) scale(0.925);
    box-shadow: 0 3px 10px rgba(15, 23, 42, 0.05);
  }
  72% {
    opacity: 1;
    transform: translateY(1px) scale(1.012);
    box-shadow: 0 16px 38px rgba(15, 23, 42, 0.17);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
    box-shadow: var(--pm-shadow, 0 10px 30px rgba(15, 23, 42, 0.14));
  }
}

/* ── KI-Schreibprompt ───────────────────────────────────────────────────── */
.pm-ai-prompt {
  width: 390px;
  max-width: calc(100% - 16px);
  padding: 10px;
  overflow: hidden;
  transition: border-color 180ms ease, box-shadow 180ms ease;
}
.pm-ai-prompt.is-generating {
  border-color: color-mix(in srgb, var(--pm-accent, #006b75) 48%, var(--pm-divider, #d8dfe1));
  box-shadow:
    var(--pm-shadow, 0 10px 30px rgba(15, 23, 42, 0.14)),
    0 0 0 1px color-mix(in srgb, var(--pm-accent, #006b75) 8%, transparent);
}
.pm-ai-prompt__head {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 1px 2px 8px;
  color: var(--pm-muted, #535e62);
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.68rem; font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase;
}
.pm-ai-prompt__head > span { display: inline-flex; align-items: center; gap: 6px; }
.pm-ai-prompt__icon { color: var(--pm-accent, #006b75); }
.pm-ai-prompt__close {
  width: 24px; height: 24px; display: grid; place-items: center;
  border: 0; border-radius: 6px; background: transparent;
  color: var(--pm-muted, #535e62); cursor: pointer; font-size: 1.05rem;
}
.pm-ai-prompt__close:hover { background: color-mix(in srgb, var(--pm-divider, #d8dfe1) 45%, transparent); }
.pm-ai-prompt__context {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: -2px 0 8px;
  color: var(--pm-muted, #535e62);
  font-size: 0.66rem;
  line-height: 1.25;
}
.pm-ai-prompt__context > span {
  width: 5px;
  height: 5px;
  flex: 0 0 5px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.55;
}
.pm-ai-prompt__context.is-selection { color: var(--pm-accent-strong, #00555f); }
.pm-ai-prompt__input-row { display: flex; align-items: center; gap: 7px; }
.pm-ai-prompt__input-row input {
  min-width: 0; height: 38px; flex: 1;
  border: 1px solid var(--pm-divider, #d8dfe1); border-radius: 8px;
  background: var(--pm-content-surface, #fff); color: var(--pm-text, #0e181b);
  outline: none; padding: 0 11px; font: inherit; font-size: 0.88rem;
}
.pm-ai-prompt__input-row input:focus { border-color: var(--pm-accent, #006b75); box-shadow: 0 0 0 2px color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent); }
.pm-ai-prompt__submit {
  width: 38px; height: 38px; flex: none; display: grid; place-items: center;
  border: 0; border-radius: 8px; background: var(--pm-accent, #006b75);
  color: var(--pm-accent-contrast, #fff); cursor: pointer; font-size: 1.05rem;
}
.pm-ai-prompt__submit:disabled { cursor: default; opacity: 0.45; }
.pm-ai-prompt__progress {
  position: relative;
  height: 2px;
  margin: 7px 2px 0;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 9%, transparent);
}
.pm-ai-prompt__progress > span {
  position: absolute;
  inset: 0;
  width: 42%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--pm-accent, #006b75) 75%, white),
    transparent
  );
  animation: pm-ai-progress 1.25s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}
.pm-ai-prompt__suggestions { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
.pm-ai-prompt__suggestions button {
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 90%, transparent);
  border-radius: 999px; background: transparent; color: var(--pm-muted, #535e62);
  padding: 4px 8px; cursor: pointer; font-size: 0.69rem;
}
.pm-ai-prompt__suggestions button:hover { border-color: var(--pm-accent, #006b75); color: var(--pm-accent-strong, #00555f); }
.pm-ai-prompt__preview {
  max-height: 170px; overflow-y: auto; margin-top: 9px; padding: 9px 10px;
  border-left: 2px solid var(--pm-accent, #006b75);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 6%, transparent);
  color: var(--pm-text, #0e181b); white-space: pre-wrap; font-size: 0.82rem; line-height: 1.5;
}
.pm-ai-prompt__status { margin-top: 7px; color: var(--pm-muted, #535e62); font-size: 0.7rem; }
.pm-ai-prompt__result-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 9px;
  padding-top: 9px;
  border-top: 1px solid var(--pm-divider, #d8dfe1);
}
.pm-ai-prompt__result-actions button {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 7px;
  background: transparent;
  color: var(--pm-text, #0e181b);
  cursor: pointer;
  font: inherit;
  font-size: 0.7rem;
  font-weight: 650;
}
.pm-ai-prompt__result-actions button:hover {
  border-color: var(--pm-accent, #006b75);
  color: var(--pm-accent-strong, #00555f);
}
.pm-ai-prompt__result-actions button.is-primary {
  border-color: var(--pm-accent, #006b75);
  background: var(--pm-accent, #006b75);
  color: var(--pm-accent-contrast, #fff);
}
.pm-ai-prompt__result-actions button.is-primary:hover { filter: brightness(1.07); }
.pm-ai-prompt__error { margin-top: 8px; color: var(--pm-danger, #b42318); font-size: 0.76rem; line-height: 1.35; }
.pm-ai-prompt__spinner {
  width: 15px; height: 15px; border: 2px solid currentColor; border-right-color: transparent;
  border-radius: 50%; animation: pm-ai-spin 700ms linear infinite;
}
@keyframes pm-ai-spin { to { transform: rotate(360deg); } }
@keyframes pm-ai-progress {
  from { transform: translateX(-120%); }
  to { transform: translateX(340%); }
}

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
  .pm-bubble__btn,
  .note-editor__toolbar-btn { transition: none; }

  .note-editor__toolbar {
    transition: none;
  }

  .pm-ai-prompt__spinner,
  .pm-ai-prompt__progress > span,
  .pm-slash--commands,
  .pm-table-handle { animation: none; }

  .pm-slash__selection,
  .pm-slash__chip,
  .pm-table-handle { transition: none; }

  .note-editor :deep(.pm-history-flash) { animation: none; }
}

:global(.pm-no-animations) .note-editor__toolbar {
  transition: none;
}

:global(.pm-no-animations) .pm-ai-prompt__spinner,
:global(.pm-no-animations) .pm-ai-prompt__progress > span {
  animation: none;
}

:global(.pm-no-animations) .pm-slash--commands {
  animation: none;
}

:global(.pm-no-animations) .pm-table-handle {
  animation: none;
  transition: none;
}

:global(.pm-no-animations) .pm-slash__selection {
  transition: none;
}

:global(.pm-no-animations) .pm-slash__chip {
  transition: none;
}

:global(.pm-no-animations) .note-editor :deep(.pm-history-flash) {
  animation: none;
}

@media (max-width: 1050px) {
  .note-editor__toolbar {
    gap: 4px;
    max-width: calc(100% - 24px);
    margin-inline: auto;
    padding-inline: 5px;
  }

  .note-editor__toolbar-divider {
    margin-inline: 0;
  }

  .note-editor__toolbar-btn {
    width: 29px;
  }

  .note-editor__toolbar-btn--text { width: 35px; }
  .note-editor__toolbar-btn--wide { width: 42px; }
}
</style>
