import test from "node:test";
import assert from "node:assert/strict";

import {
  escapeHtml,
  parsePrefix,
  matchEntry,
  buildGroups,
} from "../src/components/commandPalette/matching.js";

const MODES = { ">": "action", "#": "tag", "@": "correspondent" };

const ENTRIES = [
  { id: "a1", group: "action", label: "Dokument importieren", keywords: ["scan", "import"] },
  { id: "a2", group: "action", label: "Einstellungen öffnen", keywords: ["settings"] },
  { id: "n1", group: "nav", label: "Übersicht", keywords: ["dashboard"] },
  { id: "d1", group: "document", label: "Rechnung Stadtwerke" },
  { id: "d2", group: "document", label: "Mietvertrag" },
];

const ORDER = [
  { key: "action", label: "Aktionen" },
  { key: "nav", label: "Springe zu" },
  { key: "document", label: "Dokumente", limit: 1 },
];

test("escapeHtml escapes html-sensitive characters", () => {
  assert.equal(
    escapeHtml('<a href="x">&\'</a>'),
    "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;"
  );
});

test("parsePrefix recognizes prefixes and strips them", () => {
  assert.deepEqual(parsePrefix(">tag", MODES), { mode: ">", term: "tag" });
  assert.deepEqual(parsePrefix("#steuer", MODES), { mode: "#", term: "steuer" });
  assert.deepEqual(parsePrefix("@acme", MODES), { mode: "@", term: "acme" });
});

test("parsePrefix without a prefix returns null mode and a trimmed term", () => {
  assert.deepEqual(parsePrefix("  hallo  ", MODES), { mode: null, term: "hallo" });
  assert.deepEqual(parsePrefix("", MODES), { mode: null, term: "" });
});

test("parsePrefix trims whitespace after the prefix", () => {
  assert.deepEqual(parsePrefix("#  steuer ", MODES), { mode: "#", term: "steuer" });
});

test("matchEntry highlights subsequence hits with <mark>", () => {
  const result = matchEntry({ label: "Papierkorb" }, "papier");
  assert.equal(result.ok, true);
  assert.equal(
    result.html,
    "<mark>P</mark><mark>a</mark><mark>p</mark><mark>i</mark><mark>e</mark><mark>r</mark>korb"
  );
});

test("matchEntry is case-insensitive", () => {
  assert.equal(matchEntry({ label: "Dashboard" }, "DASH").ok, true);
});

test("matchEntry falls back to keyword match without highlighting", () => {
  const result = matchEntry({ label: "Dokument importieren", keywords: ["scan"] }, "scan");
  assert.equal(result.ok, true);
  assert.equal(result.html, "Dokument importieren");
});

test("matchEntry returns not-ok when neither label nor keywords match", () => {
  assert.equal(matchEntry({ label: "Papierkorb", keywords: ["trash"] }, "zzz").ok, false);
});

test("matchEntry escapes special characters around highlights", () => {
  const result = matchEntry({ label: "<x>" }, "x");
  assert.equal(result.ok, true);
  assert.equal(result.html, "&lt;<mark>x</mark>&gt;");
});

test("buildGroups keeps configured order and assigns a running flat index", () => {
  const groups = buildGroups(ENTRIES, {
    term: "",
    groupOrder: ORDER.filter((g) => g.key !== "document"),
  });
  assert.deepEqual(groups.map((g) => g.key), ["action", "nav"]);
  const flat = groups.flatMap((g) => g.items);
  assert.deepEqual(flat.map((it) => it.index), [0, 1, 2]);
});

test("buildGroups filters by subsequence across all groups", () => {
  const groups = buildGroups(ENTRIES, { term: "rechnung", groupOrder: ORDER });
  assert.deepEqual(groups.map((g) => g.key), ["document"]);
  assert.equal(groups[0].items.length, 1);
  assert.equal(groups[0].items[0].entry.id, "d1");
});

test("buildGroups restrictGroup keeps only one group", () => {
  const groups = buildGroups(ENTRIES, { term: "", restrictGroup: "action", groupOrder: ORDER });
  assert.deepEqual(groups.map((g) => g.key), ["action"]);
  assert.equal(groups[0].items.length, 2);
});

test("buildGroups applies the per-group limit", () => {
  // Both documents contain an 'e', but the document group is capped at 1.
  const groups = buildGroups(ENTRIES, { term: "e", restrictGroup: "document", groupOrder: ORDER });
  const documents = groups.find((g) => g.key === "document");
  assert.equal(documents.items.length, 1);
});

test("buildGroups omits empty groups", () => {
  const groups = buildGroups(ENTRIES, { term: "übersicht", groupOrder: ORDER });
  assert.deepEqual(groups.map((g) => g.key), ["nav"]);
});
