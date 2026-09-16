import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';

const root = new URL('../dist/', import.meta.url);
const manifest = JSON.parse(await readFile(new URL('.vite/manifest.json', root), 'utf8'));
const entry = Object.entries(manifest).find(([, chunk]) => chunk.isEntry)?.[0];
assert.ok(entry, 'Build manifest must contain an entry');
const seen = new Set();
function visit(key) {
  if (seen.has(key)) return;
  seen.add(key);
  for (const dependency of manifest[key].imports || []) visit(dependency);
}
visit(entry);
let bytes = 0;
let gzipBytes = 0;
for (const key of seen) {
  const file = manifest[key].file;
  assert.doesNotMatch(file, /pdfjs|NotesWorkspace|noteImage|html2pdf|NotesDevHarness/i,
    `Heavy feature code must not be statically imported on login: ${file}`);
  const content = await readFile(new URL(file, root));
  bytes += content.length;
  gzipBytes += gzipSync(content).length;
}
console.log(`Initial JavaScript: ${(bytes / 1024).toFixed(1)} KiB; ${(gzipBytes / 1024).toFixed(1)} KiB gzip (${seen.size} chunks)`);
assert.ok(bytes <= 600 * 1024, `Initial JS exceeds 600 KiB: ${bytes}`);
assert.ok(gzipBytes <= 200 * 1024, `Initial gzip JS exceeds 200 KiB: ${gzipBytes}`);
