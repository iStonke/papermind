import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const SRC_DIR = new URL("../src/", import.meta.url);
const ICON_PATTERN = /\bmdi-[a-z0-9-]+\b/g;
const IGNORED_ICON_NAMES = new Set(["mdi-svg"]);

function listSourceFiles(dirUrl) {
  const files = [];
  for (const entry of readdirSync(dirUrl, { withFileTypes: true })) {
    const childUrl = new URL(`${entry.name}${entry.isDirectory() ? "/" : ""}`, dirUrl);
    if (entry.isDirectory()) {
      files.push(...listSourceFiles(childUrl));
    } else if (/\.(vue|js)$/.test(entry.name)) {
      files.push(childUrl);
    }
  }
  return files;
}

function extractIconNames(source) {
  return new Set([...source.matchAll(ICON_PATTERN)].map((match) => match[0]));
}

test("all mdi icons used in source are registered in Vuetify icon map", () => {
  const sourceIcons = new Set();
  for (const fileUrl of listSourceFiles(SRC_DIR)) {
    const source = readFileSync(fileUrl, "utf8");
    for (const iconName of extractIconNames(source)) {
      if (!IGNORED_ICON_NAMES.has(iconName)) {
        sourceIcons.add(iconName);
      }
    }
  }

  const vuetifyPluginPath = join(SRC_DIR.pathname, "plugins/vuetify.js");
  const vuetifyPluginSource = readFileSync(vuetifyPluginPath, "utf8");
  const registeredIcons = new Set(
    [...vuetifyPluginSource.matchAll(/'([^']+)':\s*mdi[A-Z]/g)].map((match) => match[1])
  );

  const missingIcons = [...sourceIcons].filter((iconName) => !registeredIcons.has(iconName)).sort();
  assert.deepEqual(missingIcons, []);
});
