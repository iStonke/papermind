import { readNoteEditorSource } from './helpers/noteEditorSource.mjs';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const editorSource = await readNoteEditorSource();
const taskItemSource = await readFile(
  new URL('../src/components/notes/nodes/TaskItemView.vue', import.meta.url),
  'utf8',
);
const previewSource = await readFile(
  new URL('../src/components/notes/NotePreview.vue', import.meta.url),
  'utf8',
);

test('tasks are available from the text menu and slash menu', () => {
  assert.match(editorSource, /taskList: \(\) => chain\.toggleTaskList\(\)/);
  assert.match(
    editorSource,
    /key: 'taskList', icon:[^\n]+label: 'Aufgaben'/,
  );
  assert.match(
    editorSource,
    /key: 'task',[^\n]+label: 'Aufgabenliste'[^\n]+toggleTaskList\(\)/,
  );
});

test('task controls are circular and fill when checked', () => {
  assert.match(editorSource, /input\[type="checkbox"\][\s\S]*?border-radius: 50%/);
  assert.match(
    editorSource,
    /input\[type="checkbox"\]:checked\)[\s\S]*?background: var\(--pm-accent, #006b75\)/,
  );
  assert.match(previewSource, /input\[type="checkbox"\][\s\S]*?border-radius: 50%/);
  assert.match(taskItemSource, /@change="toggle"/);
  assert.match(taskItemSource, /updateAttributes\(\{ checked: event\.target\.checked \}\)/);
  assert.match(taskItemSource, /Aufgabe als erledigt markieren/);
});

test('task rows stay date-free and align their circle with the first text line', () => {
  assert.doesNotMatch(taskItemSource, /type="date"|pm-taskitem__due|mdi-calendar-clock/);
  assert.match(
    taskItemSource,
    /\.pm-taskitem__check \{[\s\S]*?display: grid;[\s\S]*?place-items: center;[\s\S]*?height: 1\.35em;[\s\S]*?margin: 0;/,
  );
  assert.match(
    editorSource,
    /li > label\)[\s\S]*?place-items: center;[\s\S]*?height: 1\.35em;/,
  );
});
