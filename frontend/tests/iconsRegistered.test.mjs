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

  // Icons werden zentral in mdiIcons.js re-exportiert und in vuetify.js
  // automatisch zu kebab-Namen abgeleitet (siehe camelToKebab dort).
  const camelToKebab = (name) =>
    name
      .replace(/([a-z])([A-Z])/g, "$1-$2")
      .replace(/([A-Za-z])([0-9])/g, "$1-$2")
      .replace(/([0-9])([A-Z])/g, "$1-$2")
      .toLowerCase();

  const iconsModuleSource = readFileSync(join(SRC_DIR.pathname, "plugins/mdiIcons.js"), "utf8");
  const registeredIcons = new Set(
    [...iconsModuleSource.matchAll(/\bmdi[A-Z][A-Za-z0-9]*\b/g)].map((match) => camelToKebab(match[0]))
  );

  // Bewusste Aliase (kebab -> abweichendes Glyph) aus vuetify.js übernehmen.
  const vuetifyPluginSource = readFileSync(join(SRC_DIR.pathname, "plugins/vuetify.js"), "utf8");
  for (const match of vuetifyPluginSource.matchAll(/'(mdi-[a-z0-9-]+)':/g)) {
    registeredIcons.add(match[1]);
  }

  const missingIcons = [...sourceIcons].filter((iconName) => !registeredIcons.has(iconName)).sort();
  assert.deepEqual(missingIcons, []);
});
