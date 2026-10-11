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
const styles = new Set();
for (const key of seen) {
  const file = manifest[key].file;
  assert.doesNotMatch(file, /pdfjs|NotesWorkspace|noteImage|noteMath|html2pdf|NotesDevHarness/i,
    `Heavy feature code must not be statically imported on login: ${file}`);
  const content = await readFile(new URL(file, root));
  bytes += content.length;
  gzipBytes += gzipSync(content).length;
  for (const css of manifest[key].css || []) styles.add(css);
}
console.log(`Initial JavaScript: ${(bytes / 1024).toFixed(1)} KiB; ${(gzipBytes / 1024).toFixed(1)} KiB gzip (${seen.size} chunks)`);
assert.ok(bytes <= 600 * 1024, `Initial JS exceeds 600 KiB: ${bytes}`);
assert.ok(gzipBytes <= 200 * 1024, `Initial gzip JS exceeds 200 KiB: ${gzipBytes}`);
let cssBytes = 0;
let cssGzipBytes = 0;
for (const style of styles) {
  const content = await readFile(new URL(style, root));
  cssBytes += content.length;
  cssGzipBytes += gzipSync(content).length;
}
console.log(`Initial CSS: ${(cssBytes / 1024).toFixed(1)} KiB; ${(cssGzipBytes / 1024).toFixed(1)} KiB gzip`);
assert.ok(cssBytes <= 512 * 1024, `Initial CSS exceeds 512 KiB: ${cssBytes}`);
assert.ok(cssGzipBytes <= 100 * 1024, `Initial gzip CSS exceeds 100 KiB: ${cssGzipBytes}`);
