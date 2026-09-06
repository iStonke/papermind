<template>
  <div
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

      <slot />

    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  controller: { type: Object, required: true },
  readonly: Boolean,
  toolbarScrolled: Boolean,
});
const {
  toolbarEl,
  openMenu,
  toolbarCompact,
  blockStyleItems,
  listStyleItems,
  pageLayoutItems,
  toolbarCalloutOptions,
  quickBlockItems,
  overflowItems,
  insertItemDisabled,
  isBlockActive,
  toggleMenu,
  openMenuFocus,
  onMenuKeydown,
  runBlockStyle,
  currentPageLayoutColumns,
  runPageLayout,
  insertAdjacentPageLayout,
  removeCurrentPageLayout,
  runMenuItem,
  runCalloutKind,
  runQuickBlock,
  toolbarActive,
} = props.controller;
</script>

<style scoped>


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

.note-editor__toolbar-dropitem--block { font-weight: 400; }

.note-editor__toolbar-dropitem--block.is-h2 { font-size: 1.02rem; font-weight: 680; }

.note-editor__toolbar-dropitem--block.is-h3 { font-size: 0.96rem; font-weight: 650; }

.note-editor__toolbar-dropitem--block.is-h4 { font-size: 0.9rem; font-weight: 620; }

@media (prefers-reduced-motion: reduce) {
  .note-editor__toolbar-btn { transition: none; }

  .note-editor__toolbar {
    transition: none;
  }

  .note-editor__toolbar-guard {
    transition: none;
  }
}

:global(.pm-no-animations) .note-editor__toolbar {
  transition: none;
}

:global(.pm-no-animations) .note-editor__toolbar-guard {
  transition: none;
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


</style>
