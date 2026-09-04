import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const editorSource = await readFile(
  new URL('../src/components/notes/NoteEditor.vue', import.meta.url),
  'utf8',
);
const iconSource = await readFile(
  new URL('../src/plugins/mdiIcons.js', import.meta.url),
  'utf8',
);

test('toolbar menus use accessible icon-only buttons', () => {
  assert.match(editorSource, /title="Text"\s+aria-label="Text"[\s\S]*?<v-icon class="note-editor__toolbar-menu-icon" size="19">mdi-format-text/);
  assert.match(editorSource, /title="Layout"\s+aria-label="Layout"[\s\S]*?<v-icon class="note-editor__toolbar-menu-icon" size="20">mdi-view-column-outline/);
  assert.match(editorSource, /title="Einfügen"\s+aria-label="Einfügen"[\s\S]*?<v-icon class="note-editor__toolbar-menu-icon" size="19">mdi-plus-box-outline/);
  assert.match(editorSource, /title="Blöcke"\s+aria-label="Blöcke"[\s\S]*?<v-icon class="note-editor__toolbar-menu-icon" size="19">mdi-text-box-outline/);
  assert.doesNotMatch(editorSource, /note-editor__toolbar-btn-label/);
  assert.equal(editorSource.match(/class="note-editor__toolbar-menu-chevron"/g)?.length, 4);
  assert.doesNotMatch(editorSource, /mdi-dots-horizontal/);
  assert.match(iconSource, /mdiViewColumnOutline/);
  assert.match(iconSource, /mdiArrowUp/);
  assert.match(iconSource, /mdiArrowDown/);
  assert.match(iconSource, /mdiTextBoxOutline/);
  assert.match(iconSource, /mdiPlusBoxOutline/);
  assert.match(editorSource, /\.note-editor__toolbar-dropitem--block \{ font-weight: 400; \}/);
});

test('callouts and template-backed quick blocks share one conditionally grouped toolbar menu', () => {
  const quickBlockItemsSource = editorSource.match(/const quickBlockItems = computed\(\(\) => \(\[([\s\S]*?)\n\]\)\);/)?.[1] || '';
  assert.match(editorSource, /v-if="openMenu === 'blocks'"/);
  assert.match(editorSource, /note-editor__blocks-menu-heading">Hinweisblöcke/);
  assert.match(editorSource, /<template v-if="quickBlockItems\.length">[\s\S]*?note-editor__blocks-menu-heading">Schnellblöcke/);
  assert.match(editorSource, /v-for="item in quickBlockItems"/);
  assert.match(quickBlockItemsSource, /\.\.\.\(props\.blockTemplates \|\| \[\]\)\.map/);
  assert.doesNotMatch(quickBlockItemsSource, /NOTE_TEMPLATE_PRESETS/);
  assert.match(editorSource, /@click\.prevent="runQuickBlock\(item\)"/);
  assert.match(editorSource, /ed\.chain\(\)\.focus\(\)\.insertTemplateBox\(item\.preset\)\.run\(\)/);
  assert.doesNotMatch(editorSource, /openMenu === 'quick-block'/);
  assert.doesNotMatch(editorSource, /openMenu === 'callout'/);
});

test('insert menu completes the remaining insertable slash-menu elements', () => {
  const insertItemsSource = editorSource.match(/const insertItems = \[([\s\S]*?)\n\];/)?.[1] || '';
  for (const label of [
    'Hyperlink',
    'Verweis',
    'Beleg verknüpfen',
    'Aufzählung',
    'Nummerierte Liste',
    'Aufgaben',
    'Zitat',
    'Codeblock',
    'Tabelle',
    'Bild einfügen',
    'Trennlinie',
  ]) {
    assert.ok(insertItemsSource.includes(`label: '${label}'`), `${label} fehlt im Einfügen-Menü`);
  }
  assert.match(editorSource, /key: 'link'[\s\S]*?action: 'link'/);
  assert.match(editorSource, /key: 'wikiLink'[\s\S]*?action: 'target'/);
  assert.match(editorSource, /key: 'documentChip'[\s\S]*?action: 'document'/);
  assert.match(insertItemsSource, /key: 'horizontalRule'/);
  assert.match(editorSource, /horizontalRule: \(\) => chain\.setHorizontalRule\(\)/);
  assert.match(editorSource, /item\.action === 'document'[\s\S]*?openDocumentChipPicker\(\)/);
  assert.match(editorSource, /item\.action === 'target'[\s\S]*?openLinkTargetPicker\(\)/);
  assert.match(editorSource, /\.note-editor__insert-menu\s*{[\s\S]*?max-height:[\s\S]*?overflow-y:\s*auto/);
});

test('first toolbar icon aligns with the tag chip edge above it', () => {
  assert.match(editorSource, /margin: 8px 0 0 8px;/);
  assert.match(editorSource, /padding: 5px 7px 5px 0;/);
  assert.match(editorSource, /@media \(max-width: 1050px\) \{[\s\S]*?\.note-editor__toolbar \{[\s\S]*?margin-left: 8px;[\s\S]*?padding-left: 0;/);
});

test('sticky toolbar becomes subtly translucent after the editor is scrolled', () => {
  assert.match(editorSource, /:class="\{ 'is-scrolled': toolbarScrolled \}"/);
  assert.match(editorSource, /toolbarScrolled\.value = Boolean\(toolbarScrollContainer\?\.scrollTop > 2\)/);
  assert.match(editorSource, /\.note-editor__toolbar-guard\.is-scrolled \{[\s\S]*?88%, transparent[\s\S]*?backdrop-filter: blur\(9px\) saturate\(1\.06\)/);
  assert.match(editorSource, /\.note-editor__toolbar-guard\.is-scrolled::after \{[\s\S]*?78%, transparent/);
});

test('AI prompt colors the otherwise desaturated wand only after text was entered', () => {
  assert.match(editorSource, /<template v-if="aiAvailable">[\s\S]*?class="note-editor__toolbar-ai"[\s\S]*?placeholder="Einfach losschreiben …"/);
  assert.match(editorSource, /'has-prompt': Boolean\(aiPrompt\.instruction\.trim\(\)\)/);
  assert.match(editorSource, /\.note-editor__toolbar-ai-icon \{[\s\S]*?color: var\(--pm-muted,[\s\S]*?opacity: 0\.74;/);
  assert.match(editorSource, /\.note-editor__toolbar-ai\.has-prompt \.note-editor__toolbar-ai-icon \{[\s\S]*?color: var\(--pm-accent,[\s\S]*?opacity: 1;/);
  assert.match(editorSource, /\.note-editor__toolbar-ai input \{[\s\S]*?border: 0;[\s\S]*?background: transparent;/);
  assert.doesNotMatch(editorSource, /\.note-editor__toolbar-btn--ai/);
});

test('AI prompt consumes the complete toolbar width instead of using an artificial cap', () => {
  assert.match(editorSource, /\.note-editor__toolbar \{[\s\S]*?width: calc\(100% - 16px\);[\s\S]*?max-width: calc\(100% - 16px\);/);
  assert.match(editorSource, /\.note-editor__toolbar-ai \{[\s\S]*?width: auto;[\s\S]*?min-width: 0;[\s\S]*?flex: 1 1 auto;/);
  assert.doesNotMatch(editorSource, /width: clamp\(150px, 24vw, 270px\)/);
});
