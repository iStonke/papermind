import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  compareDossiers,
  dossierElementsSummary,
  dossierMatchesOverview,
  filterAndSortDossiers,
} from '../src/utils/dossierOverview.js';

const workspaceSource = await readFile(new URL('../src/views/DossierWorkspace.vue', import.meta.url), 'utf8');

const entries = [
  {
    id: 'older-favorite',
    title: 'Auto',
    description: 'Versicherung und Werkstatt',
    top_note: 'Termin HU',
    item_count: 5,
    document_count: 3,
    is_favorite: true,
    archived_at: null,
    updated_at: '2026-08-01T10:00:00Z',
  },
  {
    id: 'newer',
    title: 'Steuer 2025',
    item_count: 8,
    document_count: 8,
    is_favorite: false,
    archived_at: null,
    updated_at: '2026-08-08T10:00:00Z',
  },
  {
    id: 'archived',
    title: 'Altes Auto',
    item_count: 2,
    document_count: 1,
    is_favorite: false,
    archived_at: '2026-07-01T10:00:00Z',
    updated_at: '2026-07-01T10:00:00Z',
  },
];

test('overview search includes top-note text', () => {
  assert.equal(dossierMatchesOverview(entries[0], { query: 'termin hu' }), true);
  assert.equal(dossierMatchesOverview(entries[1], { query: 'termin hu' }), false);
});

test('archive state excludes active dossiers and all excludes archived dossiers', () => {
  assert.deepEqual(
    filterAndSortDossiers(entries, { state: 'archived' }).map((entry) => entry.id),
    ['archived'],
  );
  assert.deepEqual(
    filterAndSortDossiers(entries, { state: 'all' }).map((entry) => entry.id),
    ['newer', 'older-favorite'],
  );
});

test('favorite sort is stable within favorite buckets', () => {
  const sorted = [...entries.slice(0, 2)].sort((left, right) => compareDossiers(left, right, 'favorites_first'));
  assert.deepEqual(sorted.map((entry) => entry.id), ['older-favorite', 'newer']);
});

test('element summary separates documents from notes and links', () => {
  assert.equal(dossierElementsSummary(entries[0]), '5 · 3 PDF, 2 Notizen/Links');
  assert.equal(
    dossierElementsSummary({ item_count: 6, document_count: 3, image_count: 1 }),
    '6 · 3 PDF, 1 Bild, 2 Notizen/Links',
  );
  assert.equal(dossierElementsSummary({ item_count: 0, document_count: 0 }), '0 Elemente');
});

test('the true empty overview renders only the creation empty state', () => {
  assert.match(workspaceSource, /<header v-if="showOverviewControls" class="dsr-ov__head">/);
  assert.match(workspaceSource, /<div v-if="showOverviewControls" class="dsr-ov__filters">/);
  // Kopf/Filter hängen an `listLoaded` (nicht am flüchtigen `loading`), damit stille
  // Hintergrund-Refreshes die Kopfzeile nicht kurz ausblenden.
  assert.match(workspaceSource, /const showOverviewControls = computed\(\(\) => listLoaded\.value && !isTrueOverviewEmpty\.value\)/);
  assert.match(workspaceSource, /&& dossiers\.value\.length === 0/);
  assert.doesNotMatch(workspaceSource, /dsr-ov__head--empty/);
});

test('dossier boards offer native JPEG and PNG image cards', () => {
  assert.match(workspaceSource, /title="Bild\/Foto" @click="imageUploadInput\?\.click\(\)"/);
  assert.match(workspaceSource, /accept="image\/jpeg,image\/png,\.jpg,\.jpeg,\.png"/);
  assert.match(workspaceSource, /image:\s*{ w: 236, h: 224 }/);
  assert.match(workspaceSource, /it\.item_type === 'image'/);
  assert.match(workspaceSource, /await dossierStore\.addImage\(dossierId\.value, file\)/);
});

test('the empty board previews all addable element types without changing the overview placeholder', () => {
  assert.match(
    workspaceSource,
    /<section v-if="!items\.length"[\s\S]*?dsr-board-empty__visual--elements[\s\S]*?dsr-board-empty__element--document[\s\S]*?mdi-file-document-outline[\s\S]*?dsr-board-empty__element--image[\s\S]*?mdi-image-outline[\s\S]*?dsr-board-empty__element--note[\s\S]*?mdi-note-outline[\s\S]*?dsr-board-empty__element--link[\s\S]*?mdi-link-variant/,
  );
  assert.match(
    workspaceSource,
    /v-if="isTrueOverviewEmpty" class="dsr-board-empty__visual dsr-overview-empty__visual"[\s\S]*?dsr-board-empty__sheet--note[\s\S]*?dsr-board-empty__sheet--document[\s\S]*?dsr-board-empty__sheet--link/,
  );
  assert.doesNotMatch(
    workspaceSource,
    /v-if="isTrueOverviewEmpty" class="[^"]*dsr-board-empty__visual--elements/,
  );
});

test('overview avoids skeleton/empty flash on area entry', () => {
  // Skeleton nur beim allerersten Laden und nur, wenn es die Verzögerung übersteigt.
  assert.match(workspaceSource, /const showOverviewSkeleton = computed\(\(\) => loading\.value && !listLoaded\.value && skeletonDelayElapsed\.value\)/);
  assert.match(workspaceSource, /<div v-if="showOverviewSkeleton" class="dsr-overview-grid dsr-overview-grid--loading"/);
  // Leerzustand erst nach dem ersten Laden – vorher bleibt der Bereich neutral leer.
  assert.match(workspaceSource, /const showOverviewEmpty = computed\(/);
  assert.match(workspaceSource, /<div v-else-if="showOverviewEmpty" class="dossier-empty dossier-empty--overview">/);
  // Kein direktes `v-if="loading"` mehr am Skeleton-Block.
  assert.doesNotMatch(workspaceSource, /<div v-if="loading" class="dsr-overview-grid dsr-overview-grid--loading"/);
});
