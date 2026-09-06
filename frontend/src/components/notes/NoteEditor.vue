<!--
  NoteEditor — M0 (editor-first): eine ruhige, papierartige Schreibfläche auf
  TipTap/ProseMirror. Persistenz-agnostisch: gibt Titel + Body-JSON nach außen,
  das Speichern (localStorage in M0, Backend ab M2) übernimmt der Aufrufer.

  Bewusst OHNE tippy: Bubble- und Slash-Menü sind selbst positionierte Elemente
  INNERHALB von .papermind-app, damit die --pm-*-Kontur-Tokens greifen. Die
  schlanke KI-Eingabe sitzt dauerhaft und ohne eigene Chrome in der Werkzeugleiste.
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

    <div
      v-if="workspace"
      class="note-editor__toolbar-guard"
      :class="{ 'is-scrolled': toolbarScrolled }"
    >
      <div
        ref="toolbarEl"
        class="note-editor__toolbar"
        :class="{ 'is-compact': toolbarCompact }"
        role="toolbar"
        aria-label="Text formatieren"
        :aria-disabled="readonly ? 'true' : undefined"
        :inert="readonly ? '' : undefined"
      >
      <div class="note-editor__toolbar-menu">
        <button
          type="button"
          class="note-editor__toolbar-btn note-editor__toolbar-btn--group"
          :class="{ 'is-open': openMenu === 'block' }"
          :aria-expanded="openMenu === 'block' ? 'true' : 'false'"
          aria-haspopup="menu"
          aria-controls="note-editor-menu-text"
          title="Text"
          aria-label="Text"
          @mousedown.prevent
          @click.prevent="toggleMenu('block')"
          @keydown.down.prevent="openMenuFocus('block', 'first')"
          @keydown.up.prevent="openMenuFocus('block', 'last')"
        >
          <v-icon class="note-editor__toolbar-menu-icon" size="20">mdi-text-box-outline</v-icon>
          <v-icon class="note-editor__toolbar-menu-chevron" size="12">mdi-chevron-down</v-icon>
        </button>
        <div v-if="openMenu === 'block'" id="note-editor-menu-text" role="menu" aria-label="Text" class="note-editor__toolbar-dropdown note-editor__text-menu" @keydown="onMenuKeydown">
          <div class="note-editor__text-menu-heading">Textart</div>
          <button
            v-for="item in blockStyleItems"
            :key="item.key"
            type="button"
            role="menuitem"
            class="note-editor__toolbar-dropitem note-editor__toolbar-dropitem--block"
            :class="[`is-${item.key}`, { 'is-active': isBlockActive(item.key) }]"
            @mousedown.prevent
            @click.prevent="runBlockStyle(item.key)"
          >{{ item.label }}</button>
          <div class="note-editor__text-menu-divider" aria-hidden="true"></div>
          <div class="note-editor__text-menu-heading">Listen</div>
          <button
            v-for="item in listStyleItems"
            :key="item.key"
            type="button"
            role="menuitem"
            class="note-editor__toolbar-dropitem"
            :class="{ 'is-active': isBlockActive(item.key) }"
            @mousedown.prevent
            @click.prevent="runBlockStyle(item.key)"
          >
            <span class="note-editor__toolbar-dropitem-glyph">
              <v-icon size="17">{{ item.icon }}</v-icon>
            </span>
            <span>{{ item.label }}</span>
          </button>
        </div>
      </div>

      <div class="note-editor__toolbar-menu">
        <button
          type="button"
          class="note-editor__toolbar-btn note-editor__toolbar-btn--group"
          :class="{ 'is-open': openMenu === 'layout' }"
          :aria-expanded="openMenu === 'layout' ? 'true' : 'false'"
          aria-haspopup="menu"
          aria-controls="note-editor-menu-layout"
          title="Layout"
          aria-label="Layout"
          @mousedown.prevent
          @click.prevent="toggleMenu('layout')"
          @keydown.down.prevent="openMenuFocus('layout', 'first')"
          @keydown.up.prevent="openMenuFocus('layout', 'last')"
        >
          <v-icon class="note-editor__toolbar-menu-icon" size="20">mdi-format-columns</v-icon>
          <v-icon class="note-editor__toolbar-menu-chevron" size="12">mdi-chevron-down</v-icon>
        </button>
        <div v-if="openMenu === 'layout'" id="note-editor-menu-layout" role="menu" aria-label="Layout" class="note-editor__toolbar-dropdown note-editor__layout-menu" @keydown="onMenuKeydown">
          <div class="note-editor__layout-menu-label">
            {{ currentPageLayoutColumns() ? 'Aktuelles Layout' : 'Layout einfügen' }}
          </div>
          <button
            v-for="item in pageLayoutItems"
            :key="item.columns"
            type="button"
            role="menuitemradio"
            class="note-editor__toolbar-dropitem"
            :class="{ 'is-active': currentPageLayoutColumns() === item.columns }"
            :aria-checked="currentPageLayoutColumns() === item.columns ? 'true' : 'false'"
            @mousedown.prevent
            @click.prevent="runPageLayout(item.columns)"
          >
            <span
              class="note-editor__layout-preview"
              :style="{ '--pm-layout-preview-columns': item.columns }"
              aria-hidden="true"
            >
              <span v-for="column in item.columns" :key="column"></span>
            </span>
            <span>{{ item.label }}</span>
          </button>
          <template v-if="currentPageLayoutColumns()">
            <div class="note-editor__layout-menu-divider" aria-hidden="true"></div>
            <div class="note-editor__layout-menu-label">Neues Layout</div>
            <button
              type="button"
              role="menuitem"
              class="note-editor__toolbar-dropitem"
              @mousedown.prevent
              @click.prevent="insertAdjacentPageLayout('before')"
            >
              <span class="note-editor__toolbar-dropitem-glyph"><v-icon size="17">mdi-arrow-up</v-icon></span>
              <span>Darüber einfügen</span>
            </button>
            <button
              type="button"
              role="menuitem"
              class="note-editor__toolbar-dropitem"
              @mousedown.prevent
              @click.prevent="insertAdjacentPageLayout('after')"
            >
              <span class="note-editor__toolbar-dropitem-glyph"><v-icon size="17">mdi-arrow-down</v-icon></span>
              <span>Darunter einfügen</span>
            </button>
            <button
              type="button"
              role="menuitem"
              class="note-editor__toolbar-dropitem note-editor__layout-remove"
              @mousedown.prevent
              @click.prevent="removeCurrentPageLayout"
            >
              <span class="note-editor__toolbar-dropitem-glyph"><v-icon size="17">mdi-view-agenda-outline</v-icon></span>
              <span>Layout auflösen</span>
            </button>
          </template>
        </div>
      </div>

      <span class="note-editor__toolbar-divider" aria-hidden="true" />

      <div class="note-editor__toolbar-menu">
        <button
          type="button"
          class="note-editor__toolbar-btn note-editor__toolbar-btn--group"
          :class="{ 'is-open': openMenu === 'insert' }"
          :aria-expanded="openMenu === 'insert' ? 'true' : 'false'"
          aria-haspopup="menu"
          aria-controls="note-editor-menu-insert"
          title="Einfügen"
          aria-label="Einfügen"
          @mousedown.prevent
          @click.prevent="toggleMenu('insert')"
          @keydown.down.prevent="openMenuFocus('insert', 'first')"
          @keydown.up.prevent="openMenuFocus('insert', 'last')"
        >
          <v-icon class="note-editor__toolbar-menu-icon" size="20">mdi-plus-box-outline</v-icon>
          <v-icon class="note-editor__toolbar-menu-chevron" size="12">mdi-chevron-down</v-icon>
        </button>
        <div v-if="openMenu === 'insert'" id="note-editor-menu-insert" role="menu" aria-label="Einfügen" class="note-editor__toolbar-dropdown note-editor__insert-menu" @keydown="onMenuKeydown">
          <button
            v-for="item in overflowItems"
            :key="item.key"
            type="button"
            role="menuitem"
            class="note-editor__toolbar-dropitem"
            :class="{ 'is-active': item.name ? toolbarActive(item.name) : false }"
            :disabled="insertItemDisabled(item)"
            @mousedown.prevent
            @click.prevent="runMenuItem(item)"
          >
            <span class="note-editor__toolbar-dropitem-glyph">
              <v-icon v-if="item.icon" size="17">{{ item.icon }}</v-icon>
              <span v-else class="note-editor__toolbar-dropitem-text">{{ item.glyph }}</span>
            </span>
            <span>{{ item.label }}</span>
          </button>
        </div>
      </div>

      <div class="note-editor__toolbar-menu">
        <button
          type="button"
          class="note-editor__toolbar-btn note-editor__toolbar-btn--group"
          :class="{
            'is-open': openMenu === 'blocks',
            'is-active': toolbarActive('callout') || toolbarActive('templateBox'),
          }"
          :aria-expanded="openMenu === 'blocks' ? 'true' : 'false'"
          aria-haspopup="menu"
          aria-controls="note-editor-menu-blocks"
          title="Blöcke"
          aria-label="Blöcke"
          @mousedown.prevent
          @click.prevent="toggleMenu('blocks')"
          @keydown.down.prevent="openMenuFocus('blocks', 'first')"
          @keydown.up.prevent="openMenuFocus('blocks', 'last')"
        >
          <v-icon class="note-editor__toolbar-menu-icon" size="20">mdi-view-agenda-outline</v-icon>
          <v-icon class="note-editor__toolbar-menu-chevron" size="12">mdi-chevron-down</v-icon>
        </button>
        <div v-if="openMenu === 'blocks'" id="note-editor-menu-blocks" role="menu" aria-label="Blöcke" class="note-editor__toolbar-dropdown note-editor__blocks-menu" @keydown="onMenuKeydown">
          <div class="note-editor__blocks-menu-heading">Hinweisblöcke</div>
          <button
            v-for="option in toolbarCalloutOptions"
            :key="option.value"
            type="button"
            role="menuitem"
            class="note-editor__toolbar-dropitem"
            :class="{ 'is-active': toolbarActive('callout', { kind: option.value }) }"
            @mousedown.prevent
            @click.prevent="runCalloutKind(option.value)"
          >
            <span class="note-editor__toolbar-dropitem-glyph">
              <span class="note-editor__callout-glyph">{{ option.glyph }}</span>
            </span>
            <span>{{ option.label }}</span>
          </button>
          <template v-if="quickBlockItems.length">
            <div class="note-editor__blocks-menu-divider" aria-hidden="true"></div>
            <div class="note-editor__blocks-menu-heading">Schnellblöcke</div>
            <button
              v-for="item in quickBlockItems"
              :key="item.key"
              type="button"
              role="menuitem"
              class="note-editor__toolbar-dropitem"
              @mousedown.prevent
              @click.prevent="runQuickBlock(item)"
            >
              <span class="note-editor__toolbar-dropitem-glyph">
                <span class="note-editor__quick-block-glyph">{{ item.glyph }}</span>
              </span>
              <span>{{ item.label }}</span>
            </button>
          </template>
        </div>
      </div>

      <template v-if="aiAvailable">
        <span class="note-editor__toolbar-divider" aria-hidden="true" />
        <form
          class="note-editor__toolbar-ai"
          :class="{
            'has-prompt': Boolean(aiPrompt.instruction.trim()),
            'is-generating': aiPrompt.presentation === 'toolbar' && aiPrompt.loading,
            'has-error': aiPrompt.presentation === 'toolbar' && aiPrompt.error,
          }"
          aria-label="Mit KI schreiben"
          @submit.prevent="generateAIText"
          @pointerdown.stop="prepareToolbarAIPromptTarget"
        >
          <button type="button" ref="aiOptionsButtonEl" class="note-editor__toolbar-ai-icon"
            :class="{ 'is-open': aiOptionsOpen }" title="KI-Schreiboptionen" aria-label="KI-Schreiboptionen"
            :aria-expanded="aiOptionsOpen" aria-controls="note-ai-options" :disabled="aiPrompt.loading"
            @click="toggleAIOptions">
            <span
              v-if="aiPrompt.presentation === 'toolbar' && aiPrompt.loading"
              class="note-editor__toolbar-ai-spinner"
            ></span>
            <v-icon v-else size="18">mdi-auto-fix</v-icon>
          </button>
          <input
            ref="aiToolbarInputEl"
            v-model="aiPrompt.instruction"
            type="text"
            maxlength="2000"
            autocomplete="off"
            placeholder="Einfach losschreiben …"
            aria-label="Anweisung an die KI"
            :disabled="aiPrompt.loading"
            :aria-invalid="aiPrompt.error ? 'true' : undefined"
            :aria-describedby="aiPrompt.error ? 'note-editor-ai-error' : undefined"
            @focus="ensureToolbarAIPromptTarget"
            @keydown.esc.prevent="closeAIPrompt"
          />
          <span
            v-if="aiPrompt.presentation === 'toolbar' && aiPrompt.error"
            id="note-editor-ai-error"
            class="note-editor__toolbar-ai-error"
            role="alert"
          >{{ aiPrompt.error }}</span>
          <Transition name="pm-ai-prompt">
            <div v-if="aiOptionsOpen" id="note-ai-options" class="note-editor__ai-options"
              :style="{ left: `${aiOptionsLeft}px` }"
              role="group" aria-label="KI-Schreiboptionen" @pointerdown.stop
              @keydown.esc.stop.prevent="closeAIOptions">
              <fieldset :disabled="aiPrompt.loading">
                <legend>Antwortlänge</legend>
                <div class="note-editor__ai-lengths">
                  <button v-for="(option, index) in AI_LENGTH_OPTIONS" :key="option.label" type="button"
                    :aria-pressed="aiPrompt.lengthLevel === index" @click="aiPrompt.lengthLevel = index">{{ option.label }}</button>
                </div>
                <output>{{ activeAILengthOption.label }} · {{ activeAILengthOption.lineHint }}</output>
              </fieldset>
              <label>Kontext
                <span class="note-editor__ai-context-select">
                  <select v-model="aiPrompt.contextScope" :disabled="aiPrompt.loading">
                    <option value="selection" :disabled="!aiPrompt.selectedText">Auswahl</option>
                    <option value="before">Text bis zum Cursor</option>
                    <option value="note">Ganze Notiz</option>
                  </select>
                  <v-icon size="18" aria-hidden="true">mdi-chevron-down</v-icon>
                </span>
              </label>
              <small v-if="aiPrompt.mode === 'selection'">Das Ergebnis ersetzt die markierte Auswahl.</small>
            </div>
          </Transition>
        </form>
      </template>

      </div>
    </div>

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
            <v-icon size="17">mdi-open-in-new</v-icon><span>Öffnen</span>
          </button>
          <button type="button" @click="copyLinkTarget">
            <v-icon size="17">mdi-content-copy</v-icon><span>{{ linkEditor.copied ? 'Kopiert' : 'Kopieren' }}</span>
          </button>
          <button type="button" class="is-danger" @click="removeLink">
            <v-icon size="17">mdi-link-off</v-icon><span>Entfernen</span>
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
              <v-icon size="17">mdi-table-row-plus-after</v-icon><span>Zeile darunter</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('addColumnAfter')">
              <v-icon size="17">mdi-table-column-plus-after</v-icon><span>Spalte rechts</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('toggleHeaderRow')">
              <v-icon size="17">mdi-table-headers-eye</v-icon><span>Kopfzeile umschalten</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('toggleHeaderColumn')">
              <v-icon size="17">mdi-table-column</v-icon><span>Kopfspalte umschalten</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('deleteRow')">
              <v-icon size="17">mdi-table-row-remove</v-icon><span>Zeile löschen</span>
            </button>
            <button type="button" @mousedown.prevent="runTableCommand('deleteColumn')">
              <v-icon size="17">mdi-table-column-remove</v-icon><span>Spalte löschen</span>
            </button>
            <button type="button" class="is-danger" @mousedown.prevent="runTableCommand('deleteTable')">
              <v-icon size="17">mdi-table-remove</v-icon><span>Tabelle löschen</span>
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

      <!-- Vollständiger Dialog für explizite KI-Aufrufe am Text. Die dauerhaft
           sichtbare Toolbar-Zeile bleibt davon unabhängig kompakt. -->
      <Transition name="pm-ai-prompt">
      <form
        v-if="editor && aiPrompt.open && aiPrompt.presentation === 'dialog'"
        class="pm-float pm-ai-prompt pm-ai-prompt--writing"
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
        <fieldset class="pm-ai-prompt__length" :disabled="aiPrompt.loading">
          <legend>Antwortlänge</legend>
          <output>{{ activeAILengthOption.label }} · {{ activeAILengthOption.lineHint }}</output>
          <input
            v-model.number="aiPrompt.lengthLevel"
            type="range"
            min="0"
            :max="AI_LENGTH_OPTIONS.length - 1"
            step="1"
            aria-label="Antwortlänge"
            :aria-valuetext="`${activeAILengthOption.label}, ${activeAILengthOption.lineHint}`"
          />
          <div aria-hidden="true">
            <span v-for="option in AI_LENGTH_OPTIONS" :key="option.label">{{ option.label }}</span>
          </div>
        </fieldset>
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
          {{ aiPrompt.provider
            ? `${aiPrompt.fallbackFrom ? 'Lokaler Fallback' : providerLabel(aiPrompt.provider)} · ${aiPrompt.model}`
            : 'Modell wird gestartet …' }}
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
      </Transition>

      <!-- Der Besen öffnet die Prüfung direkt im Textfluss. Die Dekoration setzt
           nur einen temporären Anker; Vorschlag und Original werden nie vor der
           ausdrücklichen Übernahme in den Dokumentinhalt geschrieben. -->
      <Teleport v-if="editor && cleanupAnchorEl" :to="cleanupAnchorEl">
        <Transition name="pm-cleanup-review" appear>
          <section
            v-if="cleanup.open"
            class="pm-cleanup-review"
            :class="{ 'is-generating': cleanup.loading }"
            role="dialog"
            aria-label="Vorschlag · noch nicht übernommen"
            @mousedown.stop
          >
            <div class="pm-cleanup-review__head">
              <span class="pm-cleanup-review__title">
                <v-icon size="19" aria-hidden="true">mdi-auto-fix</v-icon>
                Vorschlag · noch nicht übernommen
              </span>
              <div class="pm-cleanup-review__views" role="group" aria-label="Ansicht">
                <button
                  v-for="view in cleanupViews"
                  :key="view.value"
                  type="button"
                  :class="{ 'is-active': cleanup.view === view.value }"
                  :aria-pressed="cleanup.view === view.value ? 'true' : 'false'"
                  :disabled="cleanup.loading || !cleanup.draftBlocks.length"
                  @click="cleanup.view = view.value"
                >{{ view.label }}</button>
              </div>
            </div>

            <div v-if="cleanup.loading" class="pm-cleanup-review__loading" aria-live="polite">
              <div class="pm-ai-prompt__progress" aria-hidden="true"><span></span></div>
              <span>{{ cleanup.provider
                ? `${cleanup.fallbackFrom ? 'Lokaler Fallback' : providerLabel(cleanup.provider)} · ${cleanup.model}`
                : 'Vorschlag wird erstellt …' }}</span>
            </div>

            <div v-else-if="cleanup.draftBlocks.length" class="pm-cleanup-review__content">
              <div v-if="cleanup.view === 'original'" class="pm-cleanup-review__text">
                {{ cleanupOriginalText }}
              </div>
              <div v-else-if="cleanup.view === 'diff'" class="pm-cleanup-review__text" aria-label="Vergleich">
                <template v-for="(part, index) in cleanupDiffParts" :key="index">
                  <del v-if="part.type === 'removed'">{{ part.text }}</del>
                  <ins v-else-if="part.type === 'added'">{{ part.text }}</ins>
                  <span v-else>{{ part.text }}</span>
                </template>
              </div>
              <div v-else class="pm-cleanup-review__editors">
                <textarea
                  v-for="(_block, index) in cleanup.draftBlocks"
                  :key="index"
                  v-model="cleanup.draftBlocks[index]"
                  rows="2"
                  :aria-label="cleanup.draftBlocks.length === 1 ? 'Vorschlag bearbeiten' : `Vorschlag für Absatz ${index + 1} bearbeiten`"
                  @input="cleanup.error = ''"
                ></textarea>
              </div>
            </div>

            <div v-if="cleanup.instructionOpen" class="pm-cleanup-review__instruction">
              <input
                v-model="cleanup.instruction"
                type="text"
                maxlength="600"
                placeholder="Zusätzliche Anweisung …"
                aria-label="Zusätzliche Anweisung"
                @keydown.enter.prevent="regenerateCleanup"
              />
              <button type="button" :disabled="cleanup.loading" @click="regenerateCleanup">Anwenden</button>
            </div>

            <div v-if="cleanup.error" class="pm-cleanup-review__error" role="alert">{{ cleanup.error }}</div>

            <div class="pm-cleanup-review__actions">
              <div>
                <button
                  v-if="cleanup.draftBlocks.length"
                  type="button"
                  class="is-quiet"
                  :disabled="cleanup.loading"
                  @click="regenerateCleanup"
                ><v-icon size="17">mdi-refresh</v-icon> Neu erzeugen</button>
                <button
                  v-if="cleanup.draftBlocks.length"
                  type="button"
                  class="is-quiet"
                  @click="cleanup.instructionOpen = !cleanup.instructionOpen"
                ><v-icon size="17">mdi-message-text-outline</v-icon> Anweisung ergänzen</button>
              </div>
              <div>
                <button type="button" @click="discardCleanup">Verwerfen</button>
                <button
                  type="button"
                  class="is-primary"
                  :disabled="cleanup.loading || !cleanupCanApply"
                  @click="applyCleanup"
                ><v-icon size="17">mdi-check</v-icon> Übernehmen</button>
              </div>
            </div>
          </section>
        </Transition>

        <Transition name="pm-cleanup-review">
          <div v-if="cleanupRestore.open" class="pm-cleanup-restore" role="status" aria-live="polite">
            <span>Bereinigte Fassung übernommen.</span>
            <button type="button" @click="restoreCleanupOriginal">
              <v-icon size="17">mdi-undo</v-icon> Ursprung wiederherstellen
            </button>
          </div>
        </Transition>
      </Teleport>
    </div>

    <div v-if="!workspace" class="note-editor__status">
      <span class="note-editor__save" :class="`is-${status}`">
        <span class="note-editor__dot"></span>
        {{ saveLabel }}
      </span>
      <span class="note-editor__count">{{ words }} {{ words === 1 ? 'Wort' : 'Wörter' }}</span>
    </div>

    <Teleport to="body">
      <div
        v-if="shortcutsOpen"
        class="pm-shortcuts-overlay"
        @click.self="closeShortcuts"
        @keydown.esc.prevent="closeShortcuts"
      >
          <div
            class="pm-shortcuts"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pm-shortcuts-title"
          >
            <div class="pm-shortcuts__head">
              <h2 id="pm-shortcuts-title" class="pm-shortcuts__title">Tastenkürzel</h2>
              <button
                ref="shortcutsCloseEl"
                type="button"
                class="pm-shortcuts__close"
                aria-label="Schließen"
                @click="closeShortcuts"
              >
                <v-icon size="18">mdi-close</v-icon>
              </button>
            </div>
            <div class="pm-shortcuts__grid">
              <section v-for="group in shortcutGroups" :key="group.title" class="pm-shortcuts__group">
                <h3 class="pm-shortcuts__group-title">{{ group.title }}</h3>
                <ul class="pm-shortcuts__list">
                  <li v-for="row in group.items" :key="row.label" class="pm-shortcuts__row">
                    <span class="pm-shortcuts__label">{{ row.label }}</span>
                    <span class="pm-shortcuts__keys">
                      <kbd v-for="(key, i) in row.keys" :key="i">{{ key }}</kbd>
                    </span>
                  </li>
                </ul>
              </section>
            </div>
          </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef, toRaw, watch } from 'vue';
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
import { LayoutColumn, PageLayout, pageLayoutAtSelection } from './nodes/pageLayout.js';
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
  showCleanupReviewAnchor,
} from './extensions/cleanupReviewAnchor.js';
import { MOCK_DOCUMENTS, mockLinkTargets, targetGlyph } from './mockData.js';
import { NOTE_CALLOUT_OPTIONS } from '../../utils/noteCallouts.js';
import { NOTE_WRITING_PROMPT_SUGGESTIONS_DEFAULT } from '../../constants/promptDefaults.js';
import { NOTE_TEMPLATE_PRESETS } from './nodes/noteTemplates.js';
import { normalizeNoteHref, noteHrefLabel } from '../../utils/noteLinks.js';
import {
  NOTE_SLASH_USAGE_STORAGE_KEY,
  incrementNoteSlashUsage,
  mostUsedSlashCommands,
  parseNoteSlashUsage,
} from '../../utils/noteSlashUsage.js';
import { streamNoteText, uploadNoteImage } from '../../api/notes.js';
import { menuItemsOf, nextMenuItem } from '../../utils/noteMenuNavigation.js';
import { useToolbarRoving } from '../../composables/useToolbarRoving.js';
import { noteAITextForCodeBlock, noteMarkdownToTipTap } from '../../utils/noteMarkdown.js';
import {
  CLEANUP_INPUT_LIMIT,
  CLEANUP_INSTRUCTION,
  diffCleanupText,
  formatCleanupInput,
  parseCleanupOutput,
  stripCleanupMarks,
} from '../../utils/noteCleanup.js';
import {
  NOTE_PAGE_LAYOUT_COLUMNS,
} from '../../utils/noteLayouts.js';
import { NOTE_HIGHLIGHT_COLORS } from '../../utils/noteHighlights.js';

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

const surfaceEl = ref(null);
const writingEl = ref(null);
const titleEl = ref(null);
const aiToolbarInputEl = ref(null);
const aiPromptInputEl = ref(null);
const aiOptionsButtonEl = ref(null);
const aiOptionsOpen = ref(false);
const aiOptionsLeft = ref(0);
const linkInputEl = ref(null);
const imageInputEl = ref(null);
const slashMenuEl = ref(null);
const bubbleEl = ref(null);
const cleanupAnchorEl = shallowRef(null);
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
let aiGenerationController = null;
let cleanupController = null;
let historyFlashTimer = null;
let linkCopiedTimer = null;
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
  aiGenerationController?.abort();
  cleanupController?.abort();
  editor.value?.destroy();
  toolbarScrollContainer?.removeEventListener('scroll', onEditorScroll);
  window.removeEventListener('resize', refreshBubble);
  if (toolbarScrollRestoreFrame) window.cancelAnimationFrame(toolbarScrollRestoreFrame);
  if (historyFlashTimer) window.clearTimeout(historyFlashTimer);
  if (linkCopiedTimer) window.clearTimeout(linkCopiedTimer);
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
  if (aiPrompt.open) closeAIPrompt();
  if (cleanup.open || cleanupRestore.open) closeCleanup();
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

/* ── Formatierungsleiste: Menü-Gruppen + responsive Verdichtung ──────────────
   Textstil, Layout und Einfügen bleiben als kompakte Icon-Menüs sichtbar. */
const rootEl = ref(null);
const toolbarEl = ref(null);
// Pfeiltasten-Navigation innerhalb der Formatierungsleiste (ARIA Toolbar Pattern):
// die Menü-Buttons werden zu einem einzigen Tab-Stopp gebündelt.
useToolbarRoving(toolbarEl);
const openMenu = ref(null); // 'block' | 'layout' | 'highlight' | 'insert' | 'blocks' | null
const toolbarCompact = ref(false);
const TOOLBAR_COMPACT_WIDTH = 520;

const blockStyleItems = [
  { key: 'paragraph', label: 'Fließtext' },
  { key: 'h2', label: 'Überschrift 2' },
  { key: 'h3', label: 'Überschrift 3' },
  { key: 'h4', label: 'Überschrift 4' },
  { key: 'blockquote', label: 'Zitat' },
  { key: 'codeBlock', label: 'Codeblock' },
];

const listStyleItems = [
  { key: 'bulletList', icon: 'mdi-format-list-bulleted', label: 'Aufzählung' },
  { key: 'orderedList', icon: 'mdi-format-list-numbered', label: 'Nummerierte Liste' },
  { key: 'taskList', icon: 'mdi-checkbox-blank-circle-outline', label: 'Aufgaben' },
];

const pageLayoutItems = NOTE_PAGE_LAYOUT_COLUMNS.map((columns) => ({
  columns,
  label: `${columns} ${columns === 1 ? 'Spalte' : 'Spalten'}`,
}));

const toolbarCalloutOptions = NOTE_CALLOUT_OPTIONS.filter(
  (option) => !['deadline', 'source'].includes(option.value),
);

const quickBlockItems = computed(() => ([
  ...(props.blockTemplates || []).map((template) => ({
    key: `saved-${template.id}`,
    label: template.name || template.title || 'Schnellblock',
    glyph: '▤',
    preset: {
      title: template.title || '',
      color: template.color || 'teal',
      fields: Array.isArray(template.fields) ? template.fields : [],
    },
  })),
]));

const insertItems = [
  { key: 'link', name: 'link', icon: 'mdi-link-variant', label: 'Hyperlink', action: 'link' },
  { key: 'wikiLink', glyph: '[[', label: 'Verweis', action: 'target' },
  { key: 'documentChip', icon: 'mdi-file-document-outline', label: 'Beleg verknüpfen', action: 'document' },
  { key: 'table', name: 'table', icon: 'mdi-table', label: 'Tabelle', action: 'table' },
  { key: 'image', icon: 'mdi-image-plus-outline', label: 'Bild einfügen', action: 'image', requiresNote: true },
  { key: 'horizontalRule', glyph: '―', label: 'Trennlinie' },
];

const overflowItems = computed(() => {
  const items = [];
  for (const item of insertItems) {
    if (item.requiresNote && !props.noteId) continue;
    items.push(item);
  }
  return items;
});

function insertItemDisabled(item) {
  if (item.key === 'image') return imageUploadCount.value > 0;
  if (item.action === 'document') return !docPickerItems().length;
  if (item.action === 'target') return !linkTargetItems().length;
  return false;
}

function isBlockActive(key) {
  if (key === 'paragraph') return Boolean(toolbarActive('paragraph'));
  if (['blockquote', 'codeBlock', 'bulletList', 'orderedList', 'taskList'].includes(key)) {
    return Boolean(toolbarActive(key));
  }
  const level = { h2: 2, h3: 3, h4: 4 }[key];
  return Boolean(toolbarActive('heading', { level }));
}

function toggleMenu(which) {
  aiOptionsOpen.value = false;
  openMenu.value = openMenu.value === which ? null : which;
}

// ── Tastatur-Semantik der Menü-Buttons (ARIA Menu Button Pattern) ──────────────
// Jeder Gruppen-Button ist ein Menü-Trigger; das zugehörige Dropdown hat role="menu".
const MENU_DROPDOWN_IDS = {
  block: 'note-editor-menu-text',
  layout: 'note-editor-menu-layout',
  insert: 'note-editor-menu-insert',
  blocks: 'note-editor-menu-blocks',
};

// Pfeil-runter/-hoch auf dem Button öffnet das Menü und setzt den Fokus auf den
// ersten bzw. letzten Eintrag.
function openMenuFocus(which, position = 'first') {
  openMenu.value = which;
  nextTick(() => {
    const items = menuItemsOf(document.getElementById(MENU_DROPDOWN_IDS[which]));
    if (!items.length) return;
    (position === 'last' ? items[items.length - 1] : items[0]).focus();
  });
}

// Tastatur INNERHALB eines offenen Menüs: Pfeile/Pos1/Ende rollen die Einträge,
// Escape schließt und gibt den Fokus an den Trigger zurück, Tab schließt nur.
function onMenuKeydown(event) {
  const dropdown = event.currentTarget;
  if (event.key === 'Escape') {
    event.preventDefault();
    const trigger = dropdown.previousElementSibling;
    openMenu.value = null;
    nextTick(() => trigger?.focus?.());
    return;
  }
  if (event.key === 'Tab') {
    openMenu.value = null;
    return;
  }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
  const items = menuItemsOf(dropdown);
  if (!items.length) return;
  const next = nextMenuItem(items, document.activeElement, event.key);
  if (!next) return;
  event.preventDefault();
  next.focus();
}

// ── Tastenkürzel-Übersicht ─────────────────────────────────────────────────────
const shortcutsOpen = ref(false);
const isMacKeyboard = typeof navigator !== 'undefined'
  && /Mac|iP(hone|ad|od)/.test(navigator.platform || navigator.userAgent || '');
const modKeyLabel = isMacKeyboard ? '⌘' : 'Strg';
const altKeyLabel = isMacKeyboard ? '⌥' : 'Alt';
const shiftKeyLabel = isMacKeyboard ? '⇧' : 'Umschalt';
const shortcutGroups = computed(() => [
  {
    title: 'Text',
    items: [
      { label: 'Fett', keys: [modKeyLabel, 'B'] },
      { label: 'Kursiv', keys: [modKeyLabel, 'I'] },
      { label: 'Durchgestrichen', keys: [modKeyLabel, shiftKeyLabel, 'S'] },
      { label: 'Markieren', keys: [modKeyLabel, shiftKeyLabel, 'H'] },
      { label: 'Inline-Code', keys: [modKeyLabel, 'E'] },
    ],
  },
  {
    title: 'Absätze',
    items: [
      { label: 'Überschrift 2/3/4', keys: [modKeyLabel, altKeyLabel, '2 / 3 / 4'] },
      { label: 'Fließtext', keys: [modKeyLabel, altKeyLabel, '0'] },
      { label: 'Zitat', keys: [modKeyLabel, shiftKeyLabel, 'B'] },
      { label: 'Codeblock', keys: [modKeyLabel, altKeyLabel, 'C'] },
    ],
  },
  {
    title: 'Listen',
    items: [
      { label: 'Aufzählung', keys: [modKeyLabel, shiftKeyLabel, '8'] },
      { label: 'Nummerierte Liste', keys: [modKeyLabel, shiftKeyLabel, '7'] },
    ],
  },
  {
    // Zeilenanfang-Kürzel (InputRules aus callout.js): Zeichen + Leertaste.
    title: 'Hinweisblöcke',
    items: [
      { label: 'Wichtig', keys: ['!', '␣'] },
      { label: 'Frage', keys: ['?', '␣'] },
      { label: 'Entscheidung', keys: ['=', '␣'] },
    ],
  },
  {
    title: 'Einfügen & Aktionen',
    items: [
      { label: 'Hyperlink', keys: [modKeyLabel, 'K'] },
      { label: 'Befehlsmenü', keys: ['/'] },
      { label: 'Suchen & Ersetzen', keys: [modKeyLabel, 'F'] },
      { label: 'Rückgängig', keys: [modKeyLabel, 'Z'] },
      { label: 'Wiederherstellen', keys: [modKeyLabel, shiftKeyLabel, 'Z'] },
      { label: 'Diese Übersicht', keys: [modKeyLabel, '/'] },
    ],
  },
]);
function openShortcuts() {
  openMenu.value = null;
  shortcutsOpen.value = true;
  nextTick(() => shortcutsCloseEl.value?.focus?.());
}
function closeShortcuts() {
  shortcutsOpen.value = false;
  nextTick(() => editor.value?.commands.focus());
}
const shortcutsCloseEl = ref(null);

function runBlockStyle(key) {
  openMenu.value = null;
  runToolbar(key);
}
function currentPageLayoutColumns() {
  const ed = editor.value;
  return ed ? pageLayoutAtSelection(ed.state)?.node.childCount || null : null;
}
function runPageLayout(columns) {
  openMenu.value = null;
  tableMenu.open = false;
  closeLinkEditor();
  const ed = editor.value;
  if (!ed) return;
  if (pageLayoutAtSelection(ed.state)) ed.commands.setPageLayoutColumns(columns);
  else ed.commands.insertPageLayout(columns);
  ed.commands.focus();
}
function insertAdjacentPageLayout(placement) {
  openMenu.value = null;
  const ed = editor.value;
  if (!ed) return;
  ed.commands.insertPageLayoutAdjacent(placement);
  ed.commands.focus();
}
function removeCurrentPageLayout() {
  openMenu.value = null;
  const ed = editor.value;
  if (!ed) return;
  ed.commands.unsetPageLayout();
  ed.commands.focus();
}
function isTextHighlightActive(color) {
  return Boolean(editor.value?.isActive('highlight', { color }));
}
function applyTextHighlight(color) {
  openMenu.value = null;
  editor.value?.chain().focus().setNoteHighlight(color).run();
}
function removeTextHighlight() {
  openMenu.value = null;
  editor.value?.chain().focus().unsetNoteHighlight().run();
}
function runMenuItem(item) {
  openMenu.value = null;
  if (item.action === 'table') { openTableMenu(); return; }
  if (item.action === 'link') { openLinkEditor(); return; }
  if (item.action === 'image') { openImagePicker(); return; }
  if (item.action === 'document') { openDocumentChipPicker(); return; }
  if (item.action === 'target') { openLinkTargetPicker(); return; }
  runToolbar(item.key);
}

function runCalloutKind(kind) {
  openMenu.value = null;
  const ed = editor.value;
  if (!ed) return;
  const chain = ed.chain().focus();
  if (ed.isActive('callout')) chain.setCalloutKind(kind).run();
  else chain.insertCallout(kind).run();
}

function runQuickBlock(item) {
  openMenu.value = null;
  const ed = editor.value;
  if (!ed || !item?.preset) return;
  ed.chain().focus().insertTemplateBox(item.preset).run();
}

function onToolbarOutsidePointer(event) {
  if (!event.target.closest?.('.note-editor__toolbar-ai')) aiOptionsOpen.value = false;
  if (openMenu.value && toolbarEl.value && !toolbarEl.value.contains(event.target)) {
    openMenu.value = null;
  }
}

let toolbarResizeObserver = null;
onMounted(() => {
  document.addEventListener('pointerdown', onToolbarOutsidePointer, true);
  if (rootEl.value && typeof ResizeObserver !== 'undefined') {
    toolbarResizeObserver = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect?.width || 0;
      if (width > 0) toolbarCompact.value = width < TOOLBAR_COMPACT_WIDTH;
    });
    toolbarResizeObserver.observe(rootEl.value);
  }
});
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onToolbarOutsidePointer, true);
  toolbarResizeObserver?.disconnect();
  toolbarResizeObserver = null;
});

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

/* ── KI-Schreibassistenz ─────────────────────────────────────────────────── */
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

function providerLabel(provider) {
  return { ollama: 'Lokal', openai: 'OpenAI', anthropic: 'Claude' }[provider] || 'KI';
}

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
  tableMenu.open = false;
  picker.open = false;
  bubble.show = false;
  closeLinkEditor();
  closeCleanup();
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
  openMenu.value = null;
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
  aiGenerationController?.abort();
  aiGenerationController = null;
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

/* ── Aufräumen (sinnwahrend) ────────────────────────────────────────────────
   Der Besen öffnet sofort eine Prüfung im Textfluss. Bei einer kompakten
   Textauswahl wird exakt diese Auswahl bearbeitet; ohne Auswahl weiterhin die
   losen Fließtext-Absätze der Notiz. Erst „Übernehmen“ verändert das Dokument. */
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
  cleanupController?.abort();
  cleanupController = null;
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

  slash.open = false;
  bubble.show = false;
  tableMenu.open = false;
  picker.open = false;
  closeLinkEditor();
  closeAIPrompt();

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
  cleanupController = new AbortController();
  try {
    await streamNoteText({
      instruction,
      length_instruction: '',
      note_context: '',
      selected_text: payload,
      document_context: '',
    }, {
      signal: cleanupController.signal,
      onEvent: (event) => {
        if (event.type === 'meta') {
          cleanup.provider = event.provider || '';
          cleanup.model = event.model || '';
          cleanup.fallbackFrom = event.fallback_from || '';
        } else if (event.type === 'delta') {
          cleanup.preview += event.text || '';
        }
      },
    });
    const { ok, blocks } = parseCleanupOutput(cleanup.preview, cleanup.targets.length);
    if (!ok || !stripCleanupMarks(cleanup.preview)) {
      cleanup.error = 'Das Ergebnis ließ sich nicht sicher zuordnen. Bitte erneut aufräumen oder einen kleineren Abschnitt markieren.';
    } else {
      cleanup.draftBlocks = blocks;
      cleanup.view = 'diff';
    }
  } catch (error) {
    if (error?.name !== 'AbortError' && cleanup.open) {
      cleanup.error = error?.message || 'Aufräumen fehlgeschlagen.';
    }
  } finally {
    cleanup.loading = false;
    cleanupController = null;
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
  emit('history-checkpoint', 'ai');
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
  emit('history-checkpoint', 'ai');
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
  emit('history-checkpoint', 'ai');
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
  aiGenerationController = new AbortController();

  try {
    await streamNoteText({
      instruction,
      length_instruction: activeAILengthOption.value.instruction,
      note_context: aiPrompt.presentation === 'toolbar'
        ? (aiPrompt.contextScope === 'selection' ? '' : contextText)
        : (aiPrompt.mode === 'selection' ? '' : noteContextBeforeAnchor(ed)),
      context_scope: wholeNote ? 'note' : 'before',
      selected_text: aiPrompt.mode === 'selection' ? aiPrompt.selectedText : '',
      document_context: '',
    }, {
      signal: aiGenerationController.signal,
      onEvent: (event) => {
        if (event.type === 'meta') {
          aiPrompt.provider = event.provider || '';
          aiPrompt.model = event.model || '';
          aiPrompt.fallbackFrom = event.fallback_from || '';
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
    emit('history-checkpoint', 'ai');
    closeAIPrompt();
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

.note-editor__toolbar-guard {
  position: sticky;
  top: 0;
  z-index: 12;
  display: flex;
  width: 100%;
  min-height: 52px;
  flex: none;
  align-self: stretch;
  overflow: visible;
  background: var(--pm-content-surface, #fff);
  isolation: isolate;
  transition: background-color 180ms ease;
}

.note-editor__toolbar-guard.is-scrolled {
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 88%, transparent);
  -webkit-backdrop-filter: blur(9px) saturate(1.06);
  backdrop-filter: blur(9px) saturate(1.06);
}

.note-editor__toolbar-guard::after {
  position: absolute;
  z-index: 0;
  top: 100%;
  right: 0;
  left: 0;
  height: 20px;
  pointer-events: none;
  content: '';
  background: linear-gradient(
    to bottom,
    var(--pm-content-surface, #fff) 0%,
    var(--pm-content-surface, #fff) 24%,
    color-mix(in srgb, var(--pm-content-surface, #fff) 72%, transparent) 68%,
    transparent 100%
  );
}

.note-editor__toolbar-guard.is-scrolled::after {
  background: linear-gradient(
    to bottom,
    color-mix(in srgb, var(--pm-content-surface, #fff) 88%, transparent) 0%,
    color-mix(in srgb, var(--pm-content-surface, #fff) 78%, transparent) 42%,
    transparent 100%
  );
}

.note-editor__toolbar {
  position: relative;
  z-index: 1;
  display: flex;
  box-sizing: border-box;
  width: calc(100% - 16px);
  max-width: calc(100% - 16px);
  min-height: 44px;
  flex: none;
  align-self: flex-start;
  align-items: center;
  gap: 6px;
  /* Das sichtbare erste Glyph beginnt bei x=16px wie der Tag-Chip darüber:
     8px Außenabstand + 1px Rahmen + die Zentrierung im 42px-Gruppenbutton.
     Links braucht die ruhige, rahmenlose Leiste daher kein Innenpadding. */
  margin: 8px 0 0 8px;
  padding: 5px 7px 5px 0;
  /* overflow:visible, damit die Menü-Dropdowns unter der Leiste nicht
     abgeschnitten werden. Horizontales Scrollen ist dank Gruppen-Menüs +
     Compact-Modus nicht mehr nötig. */
  overflow: visible;
  /* Flach, ohne Schatten und ohne sichtbaren Rahmen. Die dezente Transparenz
     beim Scrollen kommt vom übergeordneten sticky Guard. */
  border: 1px solid transparent;
  border-radius: 12px;
  /* Ohne eigene Fläche: die Leiste übernimmt die ruhige, im gescrollten Zustand
     leicht transparente Canvas-Fläche des Guards. */
  background: transparent;
  box-shadow: none;
  scrollbar-color: color-mix(in srgb, var(--pm-muted, #535e62) 35%, transparent) transparent;
  scrollbar-width: thin;
  transition:
    background-color 220ms ease,
    border-color 220ms ease,
    box-shadow 220ms ease;
}

/* Die Leiste bleibt flach; geöffnete Dropdowns tragen ihre eigene Chrome. */

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

.note-editor__toolbar-btn:disabled {
  opacity: 0.42;
  cursor: wait;
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

/* Menü-Gruppen (Text / Layout / Einfügen) + Dropdowns */
.note-editor__toolbar-menu { position: relative; display: flex; }

.note-editor__toolbar-btn--group {
  width: 42px;
  height: 32px;
  padding: 0 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  color: var(--pm-text, #0e181b);
}
.note-editor__toolbar-menu-chevron {
  margin-left: -1px;
  opacity: 0.68;
}
.note-editor__toolbar-btn--group.is-open {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
  color: var(--pm-accent-strong, #00555f);
}
.note-editor__toolbar.is-compact .note-editor__toolbar-btn--group {
  width: 42px;
}

/* Dauerhaft sichtbarer KI-Prompt nach dem Muster einer ruhigen Suchzeile: Das
   Icon ist bewusst neutral, das Feld hat weder Rahmen noch eigene Fläche. */
.note-editor__toolbar-ai {
  position: relative;
  display: flex;
  width: auto;
  min-width: 0;
  height: 32px;
  flex: 1 1 auto;
  align-items: center;
  gap: 8px;
  color: var(--pm-muted, #535e62);
}
.note-editor__toolbar-ai-icon {
  display: grid;
  width: 22px;
  height: 32px;
  flex: none;
  place-items: center;
  color: var(--pm-muted, #748084);
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  opacity: 0.74;
  transition: color 140ms ease, opacity 140ms ease;
}
.note-editor__toolbar-ai-icon.is-open,
.note-editor__toolbar-ai-icon:hover {
  background: color-mix(in srgb, var(--pm-muted, #748084) 12%, transparent);
}
.note-editor__ai-options {
  position: absolute;
  top: calc(100% + 10px);
  z-index: 25;
  width: 310px;
  max-width: calc(100vw - 40px);
  padding: 15px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 12px;
  background: var(--pm-content-surface, #fff);
  box-shadow: var(--pm-shadow, 0 10px 30px rgba(15, 23, 42, 0.14));
  color: var(--pm-text, #0e181b);
  font-size: 0.8rem;
}
.note-editor__ai-options fieldset { padding: 0; margin: 0 0 14px; border: 0; min-width: 0; }
.note-editor__ai-options legend { margin-bottom: 7px; font-weight: 600; }
.note-editor__ai-lengths { display: flex; gap: 3px; flex-wrap: wrap; }
.note-editor__ai-lengths button {
  border: 0; border-radius: 6px; padding: 6px 8px; font: inherit;
  background: transparent; color: inherit; cursor: pointer;
}
.note-editor__ai-lengths button[aria-pressed="true"] {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
  color: var(--pm-accent-strong, #00555f);
}
.note-editor__ai-options output,
.note-editor__ai-options small { display: block; margin-top: 7px; color: var(--pm-muted, #535e62); font-size: 0.72rem; }
.note-editor__ai-options label { display: grid; gap: 7px; font-weight: 600; }
.note-editor__ai-options select {
  appearance: none;
  width: 100%; padding: 8px 36px 8px 10px; border: 1px solid var(--pm-divider, #d8dfe1); border-radius: 7px;
  background: var(--pm-content-surface, #fff); color: inherit; font: inherit; font-weight: 400;
  cursor: pointer;
  transition: border-color 140ms ease, background-color 140ms ease;
}
.note-editor__ai-context-select { position: relative; display: block; }
.note-editor__ai-context-select > .v-icon {
  position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
  color: var(--pm-muted, #535e62); pointer-events: none;
}
.note-editor__ai-options select:hover:not(:disabled) {
  border-color: var(--pm-accent, #006b75);
  background: color-mix(in srgb, var(--pm-accent, #006b75) 4%, var(--pm-content-surface, #fff));
}
.note-editor__ai-options select:focus-visible {
  outline: 2px solid var(--pm-accent, #006b75); outline-offset: 2px;
}
.note-editor__ai-options select:disabled {
  cursor: default; opacity: 0.5;
}
.note-editor__toolbar-ai.has-prompt .note-editor__toolbar-ai-icon {
  color: var(--pm-accent, #006b75);
  opacity: 1;
}
.note-editor__toolbar-ai input {
  width: 100%;
  min-width: 0;
  height: 32px;
  padding: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--pm-text, #0e181b);
  font: inherit;
  font-size: 0.9rem;
}
.note-editor__toolbar-ai input::placeholder {
  color: var(--pm-muted, #748084);
  opacity: 0.72;
}
.note-editor__toolbar-ai input:disabled { cursor: wait; }
.note-editor__toolbar-ai-spinner {
  width: 14px;
  height: 14px;
  border: 1.5px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: pm-ai-spin 700ms linear infinite;
}
.note-editor__toolbar-ai-error {
  position: absolute;
  top: calc(100% + 5px);
  left: 30px;
  z-index: 22;
  width: max-content;
  max-width: min(360px, calc(100vw - 48px));
  padding: 5px 8px;
  border: 1px solid color-mix(in srgb, var(--pm-danger, #b42318) 28%, var(--pm-divider, #d8dfe1));
  border-radius: 7px;
  background: var(--pm-content-surface, #fff);
  color: var(--pm-danger, #b42318);
  box-shadow: 0 5px 14px rgba(15, 23, 42, 0.1);
  font-size: 0.7rem;
  line-height: 1.3;
}

.note-editor__toolbar-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 20;
  min-width: 200px;
  padding: 5px;
  display: flex;
  flex-direction: column;
  gap: 1px;
  border-radius: 11px;
  background: var(--pm-content-surface, #fff);
  border: 1px solid var(--pm-divider, #d8dfe1);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.16);
}

.note-editor__insert-menu {
  max-height: min(420px, calc(100vh - 160px));
  overflow-y: auto;
  overscroll-behavior: contain;
}

.note-editor__text-menu {
  min-width: 218px;
}
.note-editor__text-menu-heading {
  padding: 6px 10px 4px;
  color: var(--pm-muted, #748084);
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.62rem;
  font-weight: 650;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.note-editor__text-menu-divider {
  height: 1px;
  margin: 6px 7px 3px;
  background: var(--pm-divider, #d8dfe1);
}

.note-editor__toolbar-dropitem {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--pm-text, #0e181b);
  font: inherit;
  font-size: 0.86rem;
  text-align: left;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}
.note-editor__toolbar-dropitem:hover { background: color-mix(in srgb, var(--pm-accent, #006b75) 9%, transparent); }
.note-editor__toolbar-dropitem.is-active { color: var(--pm-accent-strong, #00555f); background: color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent); }
.note-editor__toolbar-dropitem:disabled { opacity: 0.42; cursor: default; }
.note-editor__toolbar-dropitem-glyph {
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 22px;
  flex: none;
  color: var(--pm-muted, #535e62);
}
.note-editor__toolbar-dropitem.is-active .note-editor__toolbar-dropitem-glyph { color: var(--pm-accent, #006b75); }
.note-editor__toolbar-dropitem-text {
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.72rem;
  letter-spacing: -0.06em;
  font-weight: 680;
}

.note-editor__blocks-menu {
  min-width: 210px;
  max-height: min(460px, calc(100vh - 160px));
  overflow-y: auto;
  overscroll-behavior: contain;
}
.note-editor__blocks-menu-heading {
  padding: 6px 10px 4px;
  color: var(--pm-muted, #748084);
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.62rem;
  font-weight: 650;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.note-editor__blocks-menu-divider {
  height: 1px;
  margin: 6px 7px 3px;
  background: var(--pm-divider, #d8dfe1);
}
.note-editor__callout-glyph {
  display: inline-grid;
  width: 18px;
  height: 18px;
  place-items: center;
  border: 1px solid currentColor;
  border-radius: 5px;
  font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
}

.note-editor__quick-block-glyph {
  color: var(--pm-accent-strong, #00555f);
  font-family: ui-monospace, "SFMono-Regular", Menlo, monospace;
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
}

.note-editor__layout-menu { min-width: 190px; }
.note-editor__layout-menu-label {
  padding: 5px 10px 3px;
  color: var(--pm-muted, #748084);
  font-family: 'IBM Plex Mono', ui-monospace, monospace;
  font-size: 0.62rem;
  font-weight: 650;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.note-editor__layout-menu-divider {
  height: 1px;
  margin: 5px 7px;
  background: var(--pm-divider, #d8dfe1);
}
.note-editor__layout-remove { color: var(--pm-danger, #c84c4c); }
.note-editor__layout-remove .note-editor__toolbar-dropitem-glyph { color: currentColor; }
.note-editor__layout-preview {
  display: grid;
  grid-template-columns: repeat(var(--pm-layout-preview-columns), minmax(0, 1fr));
  gap: 2px;
  width: 24px;
  height: 17px;
  padding: 2px;
  flex: none;
  border: 1px solid currentColor;
  border-radius: 3px;
  color: var(--pm-muted, #748084);
}
.note-editor__layout-preview > span {
  min-width: 0;
  border-radius: 1px;
  background: currentColor;
  opacity: 0.48;
}
.note-editor__toolbar-dropitem.is-active .note-editor__layout-preview {
  color: var(--pm-accent, #006b75);
}

/* Absatzstil-Menü: Einträge in ihrer jeweiligen Überschriftsgröße */
.note-editor__toolbar-dropitem--block { font-weight: 400; }
.note-editor__toolbar-dropitem--block.is-h2 { font-size: 1.02rem; font-weight: 680; }
.note-editor__toolbar-dropitem--block.is-h3 { font-size: 0.96rem; font-weight: 650; }
.note-editor__toolbar-dropitem--block.is-h4 { font-size: 0.9rem; font-weight: 620; }

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
.note-editor :deep(.pm-content > * + :is(h1, h2, h3, h4, h5, h6)),
.note-editor :deep(.pm-content > :is(h1, h2, h3, h4, h5, h6) + *),
.note-editor :deep([data-layout-column] > * + :is(h1, h2, h3, h4, h5, h6)),
.note-editor :deep([data-layout-column] > :is(h1, h2, h3, h4, h5, h6) + *) {
  margin-top: var(--note-editor-heading-gap);
}
.note-editor :deep(.pm-content > :is(h1, h2, h3, h4, h5, h6):first-child),
.note-editor :deep([data-layout-column] > :is(h1, h2, h3, h4, h5, h6):first-child) {
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

/* Auswahl-Bubble: bewusst dunkel & kompakt – hebt sich klar von der hellen,
   persistenten Formatierungsleiste ab (kontextuell statt Chrome). Der dunkle
   Look bleibt in beiden Themes gleich; Rahmen + Schatten trennen ihn vom Grund. */
.pm-float.pm-bubble {
  position: fixed;
  z-index: 80;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  max-width: calc(100vw - 16px);
  padding: 3px;
  gap: 3px;
  background: #23241f;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 9px;
  box-shadow: 0 6px 22px rgba(0, 0, 0, 0.30);
}
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
.pm-link-editor__save:focus-visible {
  outline: 2px solid var(--pm-accent-strong, #00555f);
  outline-offset: 2px;
}
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

.pm-link-editor__actions button:hover,
.pm-link-editor__actions button:focus-visible {
  outline: none;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 9%, transparent);
  color: var(--pm-accent-strong, #00555f);
}

.pm-link-editor__actions button.is-danger:hover,
.pm-link-editor__actions button.is-danger:focus-visible {
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
.pm-table-menu__header-toggle:focus-visible,
.pm-table-menu__header-toggle.is-active {
  outline: none;
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
.pm-slash__group.is-frequent {
  --pm-frequent-accent: color-mix(in srgb, #8b5fbf 78%, var(--pm-text, #0e181b));
}
.pm-slash__group.is-frequent .pm-slash__group-label {
  color: var(--pm-frequent-accent);
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
.pm-slash__group.is-frequent .pm-slash__item {
  transition: color 120ms ease, background-color 140ms ease;
}
.pm-slash__group.is-frequent .pm-slash__chip {
  color: var(--pm-frequent-accent);
  border-color: color-mix(in srgb, var(--pm-frequent-accent) 30%, var(--pm-divider, #d8dfe1));
  background: color-mix(in srgb, var(--pm-frequent-accent) 8%, var(--pm-viewer-surface, #eef2f4));
}
.pm-slash__group.is-frequent .pm-slash__item:hover,
.pm-slash__group.is-frequent .pm-slash__item.is-active {
  color: var(--pm-frequent-accent);
  background: color-mix(in srgb, var(--pm-frequent-accent) 11%, transparent);
}
.pm-slash__group.is-frequent .pm-slash__item:hover .pm-slash__label,
.pm-slash__group.is-frequent .pm-slash__item.is-active .pm-slash__label {
  color: var(--pm-frequent-accent);
}
.pm-slash__group.is-frequent .pm-slash__item.is-active .pm-slash__chip {
  border-color: color-mix(in srgb, var(--pm-frequent-accent) 48%, var(--pm-divider, #d8dfe1));
  background: color-mix(in srgb, var(--pm-frequent-accent) 16%, var(--pm-viewer-surface, #eef2f4));
  box-shadow: 0 3px 10px color-mix(in srgb, var(--pm-frequent-accent) 18%, transparent);
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

/* ── Vollständiger KI-Dialog und Aufräumen-Dialog ───────────────────────── */
/* Dezentes Ein-/Ausblenden der schwebenden KI-Fenster (Schreiben + Aufräumen). */
.pm-ai-prompt-enter-active {
  transition: opacity 160ms ease, transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}
.pm-ai-prompt-leave-active {
  transition: opacity 120ms ease, transform 140ms ease;
}
.pm-ai-prompt-enter-from,
.pm-ai-prompt-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.985);
}
@media (prefers-reduced-motion: reduce) {
  .pm-ai-prompt-enter-active,
  .pm-ai-prompt-leave-active {
    transition: none;
  }
}
:global(.pm-no-animations .pm-ai-prompt-enter-active),
:global(.pm-no-animations .pm-ai-prompt-leave-active) {
  transition: none;
}

.pm-ai-prompt {
  width: 390px;
  max-width: calc(100% - 16px);
  padding: 10px;
  overflow: hidden;
  transition: border-color 180ms ease, box-shadow 180ms ease;
}
.pm-ai-prompt--writing {
  transform-origin: top left;
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
  font-family: inherit;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: normal;
  word-spacing: normal;
  text-transform: uppercase;
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
  min-width: 0;
  height: 38px;
  flex: 1;
  padding: 0 11px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 8px;
  outline: none;
  background: var(--pm-content-surface, #fff);
  color: var(--pm-text, #0e181b);
  font: inherit;
  font-size: 0.88rem;
}
.pm-ai-prompt__input-row input:focus {
  border-color: var(--pm-accent, #006b75);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
}
.pm-ai-prompt__submit {
  display: grid;
  width: 38px;
  height: 38px;
  flex: none;
  place-items: center;
  border: 0;
  border-radius: 8px;
  background: var(--pm-accent, #006b75);
  color: var(--pm-accent-contrast, #fff);
  cursor: pointer;
  font-size: 1.05rem;
}
.pm-ai-prompt__submit:disabled { cursor: default; opacity: 0.45; }
.pm-ai-prompt__length {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 4px 10px;
  min-width: 0;
  margin: 9px 2px 0;
  padding: 0;
  border: 0;
  color: var(--pm-muted, #535e62);
}
.pm-ai-prompt__length legend {
  float: left;
  padding: 0;
  font-size: 0.69rem;
  font-weight: 650;
}
.pm-ai-prompt__length output {
  justify-self: end;
  font-size: 0.67rem;
}
.pm-ai-prompt__length > input {
  grid-column: 1 / -1;
  width: 100%;
  height: 16px;
  margin: 0;
  accent-color: var(--pm-accent, #006b75);
  cursor: pointer;
}
.pm-ai-prompt__length > div {
  display: flex;
  grid-column: 1 / -1;
  justify-content: space-between;
  color: color-mix(in srgb, var(--pm-muted, #535e62) 82%, transparent);
  font-size: 0.61rem;
}
.pm-ai-prompt__length:disabled { opacity: 0.58; }
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
  padding: 4px 8px;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 90%, transparent);
  border-radius: 999px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  font-size: 0.69rem;
}
.pm-ai-prompt__suggestions button:hover {
  border-color: var(--pm-accent, #006b75);
  color: var(--pm-accent-strong, #00555f);
}
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
  width: 15px;
  height: 15px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: pm-ai-spin 700ms linear infinite;
}
@keyframes pm-ai-spin { to { transform: rotate(360deg); } }
@keyframes pm-ai-progress {
  from { transform: translateX(-120%); }
  to { transform: translateX(340%); }
}

/* ── Inline-Prüfung für „Aufräumen“ ─────────────────────────────────────── */
.note-editor :deep(.pm-cleanup-review-anchor) {
  display: block;
  width: 100%;
  margin: var(--pm-block-gap) 0;
  white-space: normal;
}

.pm-cleanup-review {
  width: 100%;
  padding: 14px 16px 12px;
  border-left: 3px solid color-mix(in srgb, var(--pm-accent, #006b75) 68%, transparent);
  border-radius: 0 12px 12px 0;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 6%, var(--pm-content-surface, #fff));
  color: var(--pm-text, #0e181b);
  font-family: inherit;
  font-size: 0.92rem;
  line-height: 1.55;
}
.pm-cleanup-review.is-generating {
  border-left-color: color-mix(in srgb, var(--pm-accent, #006b75) 88%, transparent);
}
.pm-cleanup-review__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}
.pm-cleanup-review__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--pm-accent-strong, #00555f);
  font-size: 0.82rem;
  font-weight: 650;
}
.pm-cleanup-review__views {
  display: flex;
  align-items: center;
  gap: 2px;
}
.pm-cleanup-review__views button {
  min-height: 30px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  font: inherit;
  font-size: 0.76rem;
}
.pm-cleanup-review__views button.is-active {
  background: color-mix(in srgb, var(--pm-accent, #006b75) 10%, transparent);
  color: var(--pm-accent-strong, #00555f);
}
.pm-cleanup-review__views button:disabled { cursor: default; opacity: 0.45; }
.pm-cleanup-review__loading {
  display: grid;
  gap: 8px;
  padding: 6px 0 9px;
  color: var(--pm-muted, #535e62);
  font-size: 0.74rem;
}
.pm-cleanup-review__content {
  min-height: 64px;
  padding: 2px 0 12px;
}
.pm-cleanup-review__text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.pm-cleanup-review__text del {
  border-radius: 2px;
  background: color-mix(in srgb, var(--pm-danger, #b42318) 11%, transparent);
  color: color-mix(in srgb, var(--pm-danger, #b42318) 72%, var(--pm-text, #0e181b));
  text-decoration-thickness: 1px;
}
.pm-cleanup-review__text ins {
  border-radius: 2px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 11%, transparent);
  color: inherit;
  text-decoration: none;
}
.pm-cleanup-review__editors {
  display: grid;
  gap: 8px;
}
.pm-cleanup-review__editors textarea {
  width: 100%;
  min-height: 72px;
  field-sizing: content;
  resize: vertical;
  padding: 9px 10px;
  border: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 88%, transparent);
  border-radius: 8px;
  outline: none;
  background: color-mix(in srgb, var(--pm-content-surface, #fff) 84%, transparent);
  color: inherit;
  font: inherit;
  line-height: inherit;
}
.pm-cleanup-review__editors textarea:focus,
.pm-cleanup-review__instruction input:focus {
  border-color: var(--pm-accent, #006b75);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--pm-accent, #006b75) 12%, transparent);
}
.pm-cleanup-review__instruction {
  display: flex;
  gap: 7px;
  margin: 0 0 10px;
}
.pm-cleanup-review__instruction input {
  min-width: 0;
  min-height: 34px;
  flex: 1;
  padding: 0 10px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 7px;
  outline: none;
  background: var(--pm-content-surface, #fff);
  color: inherit;
  font: inherit;
  font-size: 0.78rem;
}
.pm-cleanup-review__instruction button,
.pm-cleanup-review__actions button {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 11px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 8px;
  background: var(--pm-content-surface, #fff);
  color: var(--pm-text, #0e181b);
  cursor: pointer;
  font: inherit;
  font-size: 0.74rem;
  font-weight: 600;
}
.pm-cleanup-review__instruction button:disabled,
.pm-cleanup-review__actions button:disabled { cursor: default; opacity: 0.45; }
.pm-cleanup-review__error {
  margin: 0 0 10px;
  color: var(--pm-danger, #b42318);
  font-size: 0.76rem;
}
.pm-cleanup-review__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid color-mix(in srgb, var(--pm-divider, #d8dfe1) 78%, transparent);
}
.pm-cleanup-review__actions > div {
  display: flex;
  align-items: center;
  gap: 6px;
}
.pm-cleanup-review__actions button.is-quiet {
  border-color: transparent;
  background: transparent;
  color: var(--pm-muted, #535e62);
}
.pm-cleanup-review__actions button.is-primary {
  border-color: var(--pm-accent, #006b75);
  background: var(--pm-accent, #006b75);
  color: var(--pm-accent-contrast, #fff);
}
.pm-cleanup-restore {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 10px 13px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--pm-accent, #006b75) 7%, var(--pm-content-surface, #fff));
  color: var(--pm-muted, #535e62);
  font-size: 0.76rem;
}
.pm-cleanup-restore button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--pm-accent-strong, #00555f);
  cursor: pointer;
  font: inherit;
  font-weight: 650;
}
.pm-cleanup-review-enter-active {
  /* Keyframes starten auch beim erstmaligen Mount im ProseMirror-Anker,
     ohne auf einen bereits gezeichneten Ausgangszustand angewiesen zu sein. */
  animation: pm-cleanup-review-appear 240ms cubic-bezier(0.22, 1, 0.36, 1) both;
}
.pm-cleanup-review-leave-active {
  transition: opacity 150ms ease, transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}
.pm-cleanup-review-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}
@keyframes pm-cleanup-review-appear {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 680px) {
  .pm-cleanup-review__head,
  .pm-cleanup-review__actions { align-items: flex-start; flex-direction: column; }
  .pm-cleanup-review__actions > div { flex-wrap: wrap; }
  .pm-cleanup-review__actions > div:last-child { align-self: stretch; justify-content: flex-end; }
}

@media (prefers-reduced-motion: reduce) {
  .pm-cleanup-review-enter-active,
  .pm-cleanup-review-leave-active { animation: none; transition: none; }
}
:global(.pm-no-animations .pm-cleanup-review-enter-active),
:global(.pm-no-animations .pm-cleanup-review-leave-active) { animation: none; transition: none; }

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

  .note-editor__toolbar-guard {
    transition: none;
  }

  .note-editor__toolbar-ai-spinner,
  .pm-ai-prompt__spinner,
  .note-editor__image-spinner,
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

:global(.pm-no-animations) .note-editor__toolbar-guard {
  transition: none;
}

:global(.pm-no-animations) .note-editor__toolbar-ai-spinner,
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
    max-width: calc(100% - 16px);
    margin-right: 0;
    margin-left: 8px;
    padding-right: 5px;
    padding-left: 0;
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

/* ── Tastenkürzel-Übersicht ─────────────────────────────────────────────────── */
.pm-shortcuts-overlay {
  position: fixed;
  inset: 0;
  z-index: 2400;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: color-mix(in srgb, var(--pm-text, #0e181b) 34%, transparent);
  backdrop-filter: blur(2px);
}
.pm-shortcuts {
  width: min(900px, 100%);
  max-height: min(80vh, 640px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--pm-content-surface, #fff);
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-radius: 14px;
  box-shadow: 0 24px 60px color-mix(in srgb, var(--pm-text, #0e181b) 30%, transparent);
}
.pm-shortcuts__head {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px 13px;
  border-bottom: 1px solid var(--pm-divider, #d8dfe1);
}
.pm-shortcuts__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 680;
  color: var(--pm-text, #0e181b);
}
.pm-shortcuts__close {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--pm-muted, #535e62);
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}
.pm-shortcuts__close:hover { background: color-mix(in srgb, var(--pm-text, #0e181b) 8%, transparent); color: var(--pm-text, #0e181b); }
.pm-shortcuts__close:focus-visible { outline: 2px solid var(--pm-accent, #006b75); outline-offset: 2px; }
.pm-shortcuts__grid {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 22px 20px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px 32px;
  align-content: start;
}
.pm-shortcuts__group-title {
  margin: 4px 0 6px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--pm-muted, #535e62);
}
.pm-shortcuts__list { list-style: none; margin: 0; padding: 0; }
.pm-shortcuts__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 5px 0;
}
.pm-shortcuts__label { font-size: 0.9rem; color: var(--pm-text, #0e181b); }
.pm-shortcuts__keys { display: inline-flex; gap: 4px; flex: none; }
.pm-shortcuts__keys kbd {
  min-width: 22px;
  padding: 2px 6px;
  border-radius: 6px;
  border: 1px solid var(--pm-divider, #d8dfe1);
  border-bottom-width: 2px;
  background: color-mix(in srgb, var(--pm-text, #0e181b) 4%, var(--pm-content-surface, #fff));
  font: 500 0.78rem/1.4 'IBM Plex Mono', ui-monospace, monospace;
  color: var(--pm-text, #0e181b);
  text-align: center;
}
@media (max-width: 560px) {
  .pm-shortcuts__grid { grid-template-columns: 1fr; }
}
/* Eintritts-Animation per CSS-Keyframes (nicht Vue-Transition-verwaltet), damit
   das teleportierte Overlay nicht in einem Leave-Zustand hängen bleiben kann. */
.pm-shortcuts-overlay { animation: pm-shortcuts-fade 140ms ease both; }
.pm-shortcuts-overlay .pm-shortcuts { animation: pm-shortcuts-pop 170ms cubic-bezier(0.16, 1, 0.3, 1) both; }
@keyframes pm-shortcuts-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes pm-shortcuts-pop {
  from { transform: translateY(8px) scale(0.98); opacity: 0; }
  to { transform: none; opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .pm-shortcuts-overlay,
  .pm-shortcuts-overlay .pm-shortcuts { animation: none; }
}
</style>
