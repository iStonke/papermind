import test from 'node:test';
import assert from 'node:assert/strict';

import {
  compareDossiers,
  dossierElementsSummary,
  dossierMatchesOverview,
  filterAndSortDossiers,
} from '../src/utils/dossierOverview.js';

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
  assert.equal(dossierElementsSummary({ item_count: 0, document_count: 0 }), '0 Elemente');
});
