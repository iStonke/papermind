import test from "node:test";
import assert from "node:assert/strict";

import {
  SHORTCUT_ACTIONS,
  handleShortcut,
  isEditableShortcutTarget,
  matchesShortcut
} from "../src/keyboard/shortcuts.js";

function createEvent(key, target = null) {
  let prevented = false;
  let stopped = false;
  return {
    key,
    target,
    preventDefault() {
      prevented = true;
    },
    stopPropagation() {
      stopped = true;
    },
    get prevented() {
      return prevented;
    },
    get stopped() {
      return stopped;
    }
  };
}

test("matchesShortcut maps central activation keys", () => {
  assert.equal(matchesShortcut(createEvent("Enter"), SHORTCUT_ACTIONS.ACTIVATE), true);
  assert.equal(matchesShortcut(createEvent(" "), SHORTCUT_ACTIONS.ACTIVATE), true);
  assert.equal(matchesShortcut(createEvent("Spacebar"), SHORTCUT_ACTIONS.ACTIVATE), true);
  assert.equal(matchesShortcut(createEvent("Escape"), SHORTCUT_ACTIONS.ACTIVATE), false);
});

test("isEditableShortcutTarget detects text editing targets", () => {
  assert.equal(isEditableShortcutTarget({ tagName: "INPUT" }), true);
  assert.equal(isEditableShortcutTarget({ tagName: "textarea" }), true);
  assert.equal(isEditableShortcutTarget({ tagName: "select" }), true);
  assert.equal(isEditableShortcutTarget({ tagName: "div", isContentEditable: true }), true);
  assert.equal(isEditableShortcutTarget({ tagName: "button" }), false);
});

test("handleShortcut runs handlers and respects editable targets", () => {
  let calls = 0;
  const inputTarget = { tagName: "input" };
  const ignoredEvent = createEvent("Enter", inputTarget);
  const handledEvent = createEvent("Enter", inputTarget);

  assert.equal(handleShortcut(ignoredEvent, SHORTCUT_ACTIONS.PRIMARY, () => { calls += 1; }), false);
  assert.equal(calls, 0);
  assert.equal(ignoredEvent.prevented, false);

  assert.equal(
    handleShortcut(handledEvent, SHORTCUT_ACTIONS.PRIMARY, () => { calls += 1; }, { ignoreEditable: false, stop: true }),
    true
  );
  assert.equal(calls, 1);
  assert.equal(handledEvent.prevented, true);
  assert.equal(handledEvent.stopped, true);
});
