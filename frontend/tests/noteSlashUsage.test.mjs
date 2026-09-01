import assert from 'node:assert/strict';
import test from 'node:test';

import {
  DEFAULT_FREQUENT_SLASH_COMMAND_KEYS,
  incrementNoteSlashUsage,
  mostUsedSlashCommands,
  parseNoteSlashUsage,
} from '../src/utils/noteSlashUsage.js';

const commands = [
  { key: 'template-meeting' },
  { key: 'beleg' },
  { key: 'callout-important' },
  { key: 'h2' },
  { key: 'h3' },
  { key: 'ul' },
  { key: 'task' },
  { key: 'table' },
];

test('frequent slash commands start with five useful defaults', () => {
  assert.deepEqual(DEFAULT_FREQUENT_SLASH_COMMAND_KEYS, [
    'h2',
    'ul',
    'task',
    'callout-important',
    'beleg',
  ]);
  assert.deepEqual(
    mostUsedSlashCommands(commands, {}).map((command) => command.key),
    DEFAULT_FREQUENT_SLASH_COMMAND_KEYS,
  );
});
test('actual usage outranks defaults and remains limited to five commands', () => {
  const usage = { table: 8, h3: 3, beleg: 1 };
  const result = mostUsedSlashCommands(commands, usage);

  assert.equal(result.length, 5);
  assert.deepEqual(result.slice(0, 3).map((command) => command.key), [
    'table',
    'h3',
    'beleg',
  ]);
});

test('usage counters are validated and incremented without mutating their input', () => {
  assert.deepEqual(parseNoteSlashUsage('{"h2":2,"bad":-1,"float":1.5}'), { h2: 2 });
  assert.deepEqual(parseNoteSlashUsage('not-json'), {});

  const current = { h2: 2 };
  const updated = incrementNoteSlashUsage(current, 'h2');
  assert.deepEqual(updated, { h2: 3 });
  assert.deepEqual(current, { h2: 2 });
});
