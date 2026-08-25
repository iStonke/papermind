import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [globalStyleSource, documentsSource, notesSource, noteEditorSource, actionIconSource, designSource] = await Promise.all([
  readFile(new URL('../src/style.css', import.meta.url), 'utf8'),
  readFile(new URL('../src/views/DocumentsWorkspace.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/views/NotesWorkspace.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/notes/NoteWorkspaceEditor.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/PmActionIcon.vue', import.meta.url), 'utf8'),
  readFile(new URL('../../docs/design/README.md', import.meta.url), 'utf8'),
]);

test('compact header actions share one fixed tonal icon-button geometry', () => {
  assert.match(
    globalStyleSource,
    /\.pm-header-icon-btn\.v-btn\s*\{[\s\S]*?width:\s*36px;[\s\S]*?height:\s*36px;[\s\S]*?border-radius:\s*10px;/,
  );
  assert.match(documentsSource, /list-header-viewmode--documents pm-header-icon-btn/);
  assert.equal((documentsSource.match(/knowledge-header-btn[^"\n]*pm-header-icon-btn/g) || []).length, 2);
  assert.match(notesSource, /notes-ws__manage-toggle pm-header-icon-btn/);
  assert.match(documentsSource, /<v-icon size="20">mdi-clock-outline<\/v-icon>/);
  assert.match(notesSource, /<v-icon size="20">\{\{ isManageMode/);
});

test('dense editor action groups use the quiet variant without changing geometry', () => {
  assert.match(globalStyleSource, /\.pm-header-icon-btn--quiet\.v-btn\s*\{/);
  assert.equal((noteEditorSource.match(/'pm-header-icon-btn--quiet'/g) || []).length, 4);
  assert.equal((noteEditorSource.match(/<PmActionIcon/g) || []).length, 4);
  assert.match(actionIconSource, /viewBox="0 0 24 24"/);
  assert.match(actionIconSource, /stroke-width="1\.85"/);
  assert.match(actionIconSource, /stroke-linecap="round"/);
  assert.match(actionIconSource, /size: \{ type: \[Number, String\], default: 20 \}/);
  assert.match(noteEditorSource, /class="note-workspace-editor__view-divider"/);
  assert.match(noteEditorSource, /:aria-pressed="listVisible \? 'false' : 'true'"/);
});

test('the project design guide records the compact header-action convention', () => {
  assert.match(designSource, /## Kompakte Kopfzeilenaktionen \(verbindlich\)/);
  assert.match(designSource, /Feste Geometrie: 36 × 36 px, Radius 10 px, Icon 20 px/);
  assert.match(designSource, /Icon-only-Aktionen benötigen immer ein eindeutiges `aria-label` und `title`/);
  assert.match(designSource, /pm-header-icon-btn--quiet/);
});
