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
  assert.match(editorSource, /title="Text"\s+aria-label="Text"[\s\S]*?mdi-format-text/);
  assert.match(editorSource, /title="Layout"\s+aria-label="Layout"[\s\S]*?mdi-view-column-outline/);
  assert.match(editorSource, /title="Einfügen"\s+aria-label="Einfügen"[\s\S]*?mdi-plus/);
  assert.doesNotMatch(editorSource, /note-editor__toolbar-btn-label/);
  assert.equal(editorSource.match(/class="note-editor__toolbar-menu-chevron"/g)?.length, 3);
  assert.doesNotMatch(editorSource, /mdi-dots-horizontal/);
  assert.match(iconSource, /mdiViewColumnOutline/);
  assert.match(iconSource, /mdiArrowUp/);
  assert.match(iconSource, /mdiArrowDown/);
  assert.match(editorSource, /\.note-editor__toolbar-dropitem--block \{ font-weight: 400; \}/);
});

test('first toolbar icon aligns with the tag chip edge above it', () => {
  assert.match(editorSource, /margin: 8px 0 0 8px;/);
  assert.match(editorSource, /padding: 5px 7px 5px 0;/);
  assert.match(editorSource, /@media \(max-width: 1050px\) \{[\s\S]*?\.note-editor__toolbar \{[\s\S]*?margin-left: 8px;[\s\S]*?padding-left: 0;/);
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
