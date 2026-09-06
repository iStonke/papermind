import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const nodeSource = await readFile(
  new URL('../src/components/notes/nodes/documentChip.js', import.meta.url),
  'utf8',
);
const viewSource = await readFile(
  new URL('../src/components/notes/nodes/DocumentChipView.vue', import.meta.url),
  'utf8',
);

test('new document chips enter once with a PaperMind accent transition', () => {
  assert.match(nodeSource, /insertedAt: \{ default: null, rendered: false \}/);
  assert.match(nodeSource, /attrs: \{ \.\.\.attrs, insertedAt: new Date\(\)\.toISOString\(\) \}/);
  assert.match(viewSource, /'is-arriving': isArriving/);
  assert.match(viewSource, /props\.editor\.isEditable/);
  assert.match(viewSource, /Math\.abs\(Date\.now\(\) - insertedAt\) <= 4000/);
  assert.match(viewSource, /@keyframes pm-docchip-arrive/);
  assert.match(viewSource, /@keyframes pm-docchip-ring/);
  assert.match(viewSource, /@keyframes pm-docchip-icon/);
});

test('document chip arrival feedback respects reduced-motion settings', () => {
  assert.match(viewSource, /prefers-reduced-motion: reduce[\s\S]*?pm-docchip\.is-arriving/);
  assert.match(viewSource, /pm-no-animations[\s\S]*?pm-docchip\.is-arriving/);
});

test('document chip is keyboard operable and announced as a button', () => {
  assert.match(viewSource, /role="button"/);
  assert.match(viewSource, /tabindex="0"/);
  assert.match(viewSource, /:aria-label="`Beleg öffnen: \$\{node\.attrs\.title \|\| 'Beleg'\}`"/);
  assert.match(viewSource, /@keydown\.enter\.prevent="open"/);
  assert.match(viewSource, /@keydown\.space\.prevent="open"/);
  assert.match(viewSource, /\.pm-docchip:focus-visible \{/);
});
