import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const [routerSource, notesStoreSource, widgetSource, dashboardSource, dashboardStoreSource, noteServiceSource] = await Promise.all([
  readFile(new URL('../../backend/app/routers/notes.py', import.meta.url), 'utf8'),
  readFile(new URL('../src/stores/notes.js', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/dashboard/OpenTasksWidget.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/views/DashboardView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../src/stores/dashboard.js', import.meta.url), 'utf8'),
  readFile(new URL('../../backend/app/services/note_service.py', import.meta.url), 'utf8'),
]);

test('dashboard task toggle returns and caches the updated canonical note', () => {
  assert.match(
    routerSource,
    /"\/{note_id}\/tasks\/toggle",[\s\S]*?response_model=NoteRead[\s\S]*?return NoteRead\.model_validate\(note\)/,
  );
  assert.match(
    notesStoreSource,
    /async function toggleTask\(id, position, done = true\) \{[\s\S]*?syncServerNote\(await api\.toggleNoteTask\(id, position, done\)\)/,
  );
  assert.match(widgetSource, /await notesStore\.toggleTask\(task\.note_id, task\.position, newDone\)/);
  assert.doesNotMatch(widgetSource, /import \{ toggleNoteTask \}/);
});

test('both editing directions write task state into the note body', () => {
  assert.match(
    noteServiceSource,
    /if payload\.body_json is not None:[\s\S]*?note\.body_json = payload\.body_json[\s\S]*?self\._sync_tasks\(note\)/,
  );
  assert.match(
    noteServiceSource,
    /def set_task_checked\([\s\S]*?set_taskitem_checked\(body, position, checked\)[\s\S]*?note\.body_json = body[\s\S]*?self\._sync_tasks\(note\)/,
  );
});

test('dashboard refreshes after a note autosave completes during navigation', () => {
  assert.match(
    notesStoreSource,
    /patch\.body_json !== undefined[\s\S]*?dispatchEvent\(new CustomEvent\('papermind:note-content-saved'/,
  );
  assert.match(
    dashboardSource,
    /addEventListener\('papermind:note-content-saved', refreshAfterNoteSave\)/,
  );
  assert.match(
    dashboardSource,
    /function refreshAfterNoteSave\(\) \{[\s\S]*?dashboardStore\.fetchOverview\(\)/,
  );
  assert.match(
    dashboardStoreSource,
    /const revision = \+\+requestRevision;[\s\S]*?if \(revision !== requestRevision\) return;[\s\S]*?overview\.value =/,
  );
});
