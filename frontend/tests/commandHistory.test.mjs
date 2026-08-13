import assert from 'node:assert/strict';
import test from 'node:test';

import { useCommandHistory } from '../src/composables/useCommandHistory.js';

test('command history executes undo and redo in stack order', async () => {
  const history = useCommandHistory();
  const events = [];
  history.record({ label: 'Verschieben', undo: async () => events.push('undo-move'), redo: async () => events.push('redo-move') });
  history.record({ label: 'Bearbeiten', undo: async () => events.push('undo-edit'), redo: async () => events.push('redo-edit') });

  assert.equal(history.undoLabel.value, 'Bearbeiten');
  await history.undo();
  await history.undo();
  await history.redo();

  assert.deepEqual(events, ['undo-edit', 'undo-move', 'redo-move']);
  assert.equal(history.undoLabel.value, 'Verschieben');
  assert.equal(history.redoLabel.value, 'Bearbeiten');
});

test('new commands discard the redo branch and respect the limit', async () => {
  const history = useCommandHistory({ limit: 2 });
  const command = (label) => ({ label, undo: async () => {}, redo: async () => {} });
  history.record(command('A'));
  history.record(command('B'));
  history.record(command('C'));
  await history.undo();
  assert.equal(history.canRedo.value, true);

  history.record(command('D'));

  assert.equal(history.canRedo.value, false);
  assert.equal(history.undoLabel.value, 'D');
  await history.undo();
  assert.equal(history.undoLabel.value, 'B');
});

test('failed undo keeps the command available', async () => {
  const history = useCommandHistory();
  history.record({ label: 'Fehler', undo: async () => { throw new Error('kaputt'); }, redo: async () => {} });

  await assert.rejects(history.undo(), /kaputt/);

  assert.equal(history.canUndo.value, true);
  assert.equal(history.undoLabel.value, 'Fehler');
});
