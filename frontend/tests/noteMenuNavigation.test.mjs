import assert from 'node:assert/strict';
import test from 'node:test';
import { menuItemsOf, nextMenuItem } from '../src/utils/noteMenuNavigation.js';

function item(role, { disabled = false, ariaDisabled = null } = {}) {
  return { role, disabled, getAttribute: () => ariaDisabled };
}

test('layout radio choices and checkbox choices participate in menu navigation', () => {
  const entries = [item('menuitemradio'), item('menuitemradio'), item('menuitemcheckbox'), item('menuitem')];
  const dropdown = {
    querySelectorAll(selector) {
      return entries.filter((entry) => selector.includes(`[role="${entry.role}"]`));
    },
  };
  const items = menuItemsOf(dropdown);
  assert.deepEqual(items, entries);
  assert.equal(nextMenuItem(items, null, 'ArrowDown'), entries[0]);
  assert.equal(nextMenuItem(items, entries[0], 'ArrowUp'), entries[3]);
  assert.equal(nextMenuItem(items, entries[3], 'ArrowDown'), entries[0]);
  assert.equal(nextMenuItem(items, entries[2], 'Home'), entries[0]);
  assert.equal(nextMenuItem(items, entries[0], 'End'), entries[3]);
});

test('disabled items are skipped and empty or unrelated navigation does nothing', () => {
  const enabled = item('menuitemradio');
  const items = menuItemsOf({ querySelectorAll: () => [item('menuitem', { disabled: true }), enabled, item('menuitem', { ariaDisabled: 'true' })] });
  assert.deepEqual(items, [enabled]);
  assert.equal(nextMenuItem(items, enabled, 'ArrowDown'), enabled);
  assert.equal(nextMenuItem(items, enabled, 'a'), null);
  assert.equal(nextMenuItem([], null, 'ArrowDown'), null);
  assert.deepEqual(menuItemsOf(null), []);
});
