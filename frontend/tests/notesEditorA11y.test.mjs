import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (rel) => readFile(new URL(rel, import.meta.url), 'utf8');

const rovingSource = await read('../src/composables/useToolbarRoving.js');
const editorSource = await read('../src/components/notes/NoteEditor.vue');
const wikiSource = await read('../src/components/notes/nodes/WikiLinkView.vue');

test('toolbar roving composable bundles the buttons into one arrow-navigated tab stop', () => {
  // Genau ein Button tabbable, Rest per tabindex=-1 ausgeblendet.
  assert.match(rovingSource, /btn\.tabIndex = btn === target \? 0 : -1/);
  // Pfeil links/rechts + Pos1/Ende navigieren.
  assert.match(rovingSource, /\['ArrowLeft', 'ArrowRight', 'Home', 'End'\]\.includes\(event\.key\)/);
  // Text-/Editierfelder fangen die Pfeile NICHT ab (Cursor-Bewegung bleibt erhalten).
  assert.match(rovingSource, /tagName === 'INPUT'[\s\S]*?tagName === 'TEXTAREA'[\s\S]*?isContentEditable/);
  // Offene Dropdowns/Menüs werden ausgeklammert.
  assert.match(rovingSource, /note-editor__toolbar-dropdown, \[role="menu"\], \[role="listbox"\], \[role="dialog"\]/);
  // Anbindung per watch (greift auch bei v-if-Leiste, die erst nach dem Mount erscheint).
  assert.match(rovingSource, /watch\(toolbarRef, .*\{ immediate: true, flush: 'post' \}\)/);
  // Kein Layout-basierter Sichtbarkeits-Check im Filter, der beim frühen Binden
  // (ungelayoutete Leiste) alle Buttons ausschließen würde.
  assert.doesNotMatch(rovingSource, /offsetParent\s*!==?\s*null/);
  assert.doesNotMatch(rovingSource, /getClientRects\(\)\.length/);
});

test('note editor wires the roving toolbar to its toolbar ref', () => {
  assert.match(editorSource, /import \{ useToolbarRoving \} from '\.\.\/\.\.\/composables\/useToolbarRoving\.js'/);
  assert.match(editorSource, /useToolbarRoving\(toolbarEl\)/);
});

test('wiki link chip is keyboard operable and announced as a button', () => {
  assert.match(wikiSource, /role="button"/);
  assert.match(wikiSource, /tabindex="0"/);
  assert.match(wikiSource, /:aria-label="`Verweis öffnen: \$\{node\.attrs\.label\}`"/);
  assert.match(wikiSource, /@keydown\.enter\.prevent="open"/);
  assert.match(wikiSource, /@keydown\.space\.prevent="open"/);
  assert.match(wikiSource, /\.pm-wikilink:focus-visible \{/);
});

test('toolbar menu buttons follow the ARIA menu-button pattern', () => {
  // Alle vier Gruppen-Buttons als Menü-Trigger ausgezeichnet + Pfeil-öffnen.
  assert.equal((editorSource.match(/aria-haspopup="menu"/g) || []).length, 4);
  for (const id of ['note-editor-menu-text', 'note-editor-menu-layout', 'note-editor-menu-insert', 'note-editor-menu-blocks']) {
    assert.match(editorSource, new RegExp(`aria-controls="${id}"`), `${id} nicht als aria-controls verknüpft`);
    assert.match(editorSource, new RegExp(`id="${id}" role="menu"`), `${id} ohne role="menu"`);
  }
  assert.equal((editorSource.match(/@keydown\.down\.prevent="openMenuFocus\(/g) || []).length, 4);
  assert.equal((editorSource.match(/@keydown\.up\.prevent="openMenuFocus\(/g) || []).length, 4);
  // Einträge tragen menuitem-Rollen (radios für die Spaltenauswahl).
  assert.ok((editorSource.match(/role="menuitem"/g) || []).length >= 6);
  assert.match(editorSource, /role="menuitemradio"[\s\S]*?:aria-checked=/);
  // Innen-Navigation: Escape schließt und gibt Fokus zurück, Pfeile rollen.
  assert.match(editorSource, /function onMenuKeydown\(event\)/);
  assert.match(editorSource, /if \(event\.key === 'Escape'\)[\s\S]*?openMenu\.value = null[\s\S]*?trigger\?\.focus/);
  assert.match(editorSource, /\['ArrowDown', 'ArrowUp', 'Home', 'End'\]\.includes\(event\.key\)/);
});

test('keyboard shortcuts overview opens via Mod+/ and is a robust modal', () => {
  assert.match(editorSource, /\(event\.metaKey \|\| event\.ctrlKey\) && !event\.altKey && event\.key === '\/'/);
  assert.match(editorSource, /openShortcuts\(\)/);
  assert.match(editorSource, /role="dialog"\s+aria-modal="true"\s+aria-labelledby="pm-shortcuts-title"/);
  assert.match(editorSource, /<Teleport to="body">/);
  assert.match(editorSource, /@click\.self="closeShortcuts"/);
  assert.match(editorSource, /@keydown\.esc\.prevent="closeShortcuts"/);
  // Regressionsschutz: KEINE <Transition> um das teleportierte Overlay (bleibt
  // sonst in einem Leave-Zustand hängen und blockiert unsichtbar die ganze App).
  assert.doesNotMatch(editorSource, /<Transition name="pm-shortcuts">/);
  assert.match(editorSource, /@keyframes pm-shortcuts-pop/);
  // Enthält u.a. die Hinweisblock-Zeilenanfang-Kürzel (?, !, = + Leertaste).
  assert.match(editorSource, /title: 'Hinweisblöcke'[\s\S]*?label: 'Frage', keys: \['\?', '␣'\]/);
  // Breiteres Fenster + fixierte, nicht mitscrollende Titelzeile: Kopf ist
  // flex:none, nur das Grid scrollt.
  assert.match(editorSource, /\.pm-shortcuts \{[\s\S]*?width: min\(900px, 100%\)[\s\S]*?display: flex[\s\S]*?flex-direction: column[\s\S]*?overflow: hidden/);
  assert.match(editorSource, /\.pm-shortcuts__head \{[\s\S]*?flex: none[\s\S]*?border-bottom:/);
  assert.match(editorSource, /\.pm-shortcuts__grid \{[\s\S]*?overflow-y: auto[\s\S]*?grid-template-columns: repeat\(auto-fit/);
});

test('secondary menus share one icon size and expose focus-visible states', () => {
  // Icon-Größe der „Icon + Label"-Menüzeilen vereinheitlicht auf 17
  // (Tabellen-Aktionen vorher 18, Link-Aktionen vorher 16).
  for (const icon of ['mdi-table-row-plus-after', 'mdi-table-remove']) {
    assert.match(editorSource, new RegExp(`<v-icon size="17">${icon}`), `${icon} nicht auf size 17`);
  }
  for (const icon of ['mdi-open-in-new', 'mdi-content-copy', 'mdi-link-off']) {
    assert.match(editorSource, new RegExp(`<v-icon size="17">${icon}`), `${icon} nicht auf size 17`);
  }
  // Tabellen-Aktionen tragen keine size=18 mehr.
  assert.doesNotMatch(editorSource, /<v-icon size="18">mdi-table-/);

  // Fokus-Sichtbarkeit auf allen zuvor lückenhaften Bedienelementen.
  assert.match(editorSource, /\.pm-bubble__btn:focus-visible \{/);
  assert.match(editorSource, /\.pm-bubble__swatch:focus-visible \{/);
  assert.match(editorSource, /\.pm-link-editor__save:focus-visible \{/);
  assert.match(editorSource, /\.pm-link-editor__actions button:hover,\s*\.pm-link-editor__actions button:focus-visible/);
  assert.match(editorSource, /\.pm-table-menu__header-toggle:focus-visible/);
});

test('shortcuts overview is reachable from the header ⋮ menu', async () => {
  const workspaceSource = await read('../src/components/notes/NoteWorkspaceEditor.vue');
  // NoteEditor stellt openShortcuts bereit …
  assert.match(editorSource, /defineExpose\(\{[\s\S]*?openShortcuts[\s\S]*?\}\)/);
  // … der Parent ruft es über die Child-Ref auf …
  assert.match(workspaceSource, /function openNoteShortcuts\(\)\s*\{[\s\S]*?noteEditorRef\.value\?\.openShortcuts\?\.\(\)/);
  // … und bietet einen ⋮-Menüeintrag mit plattformgerechtem Kürzel-Hinweis.
  assert.match(workspaceSource, /title="Tastenkürzel"[\s\S]*?@click="openNoteShortcuts"/);
  assert.match(workspaceSource, /note-workspace-editor__more-hint">\{\{ shortcutsHint \}\}/);
  assert.match(workspaceSource, /shortcutsHint =[\s\S]*?'⌘ \/'[\s\S]*?'Strg \/'/);
});
