import test from 'node:test';
import assert from 'node:assert/strict';

import {
  collectionMemberSummaries,
  documentRhythm,
  monthlyCounts,
  seasonLabel,
  stackedYearlyCounts,
  typeBreakdown,
  yearlyCounts,
  yearRange,
} from '../src/utils/correspondentProfileStats.js';

const entry = (document_date, correspondent_id = 'org', document_type = 'Rechnung') => ({ document_date, correspondent_id, document_type });
// Autohaus-Beispiel: zwei frühe Einzelstücke, ab 2024 regelmäßig.
const activity = [
  entry('2019-08-14'),
  entry('2021-05-10', 'org', 'Kaufvertrag'),
  entry('2024-03-12', 'torge'),
  entry('2024-10-02', 'org', 'Garantieunterlagen'),
  entry('2025-04-08', 'anja', 'Kostenvoranschlag'),
  entry('2025-09-15', 'torge'),
  entry('2025-11-18', 'org', 'Auftragsbestätigung'),
  entry('2026-04-12'),
  entry('2026-09-21', 'torge'),
];

test('years run from the first document to now, split into direct and via persons', () => {
  const years = yearlyCounts(activity, 'org', { now: new Date('2026-11-03T12:00:00') });
  assert.deepEqual(years.map((y) => y.year), [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]);
  assert.deepEqual(years.find((y) => y.year === 2025), { year: 2025, own: 1, members: 2, total: 3 });
  assert.equal(years.find((y) => y.year === 2020).total, 0);
  assert.deepEqual(yearlyCounts([], 'org'), []);
});

test('only the last twelve years are shown', () => {
  const years = yearlyCounts([entry('2001-01-01'), entry('2026-01-01')], 'org', { now: new Date('2026-06-01T00:00:00') });
  assert.equal(years.length, 12);
  assert.equal(years[0].year, 2015);
  const recentOnly = yearlyCounts([entry('2026-03-01')], 'org', { now: new Date('2026-06-01T00:00:00') });
  assert.deepEqual(recentOnly.map((y) => y.year), [2022, 2023, 2024, 2025, 2026], 'at least five years');
});

test('months and seasons describe when documents arrive', () => {
  const months = monthlyCounts(activity);
  assert.equal(months.reduce((a, b) => a + b, 0), 9);
  assert.equal(months[3], 2, 'April');
  assert.equal(seasonLabel(months), 'Häufung Frühjahr und Herbst');
  assert.equal(seasonLabel([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]), '');
  assert.equal(seasonLabel([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]), 'übers Jahr verteilt');
});

test('rhythm measures the latest phase and mentions a quieter past', () => {
  const rhythm = documentRhythm(activity);
  assert.equal(rhythm.label, 'alle 5 Mon.');
  assert.equal(rhythm.detail, 'seit 2024 · vorher selten');
  assert.equal(documentRhythm(activity.slice(0, 2)), null);
  const monthly = documentRhythm([entry('2026-01-05'), entry('2026-02-04'), entry('2026-03-06'), entry('2026-04-05')]);
  assert.equal(monthly.label, 'monatlich');
  assert.equal(monthly.detail, 'gleichmäßig seit 2026');
});

test('types are counted and a long tail is folded into "Weitere"', () => {
  assert.deepEqual(typeBreakdown(activity).map((r) => [r.label, r.count]), [
    ['Rechnung', 5],
    ['Auftragsbestätigung', 1],
    ['Garantieunterlagen', 1],
    ['Kaufvertrag', 1],
    ['Kostenvoranschlag', 1],
  ]);
  const folded = typeBreakdown(activity, { limit: 3 });
  assert.deepEqual(folded.at(-1), { label: 'Weitere', count: 3, isRest: true });
  assert.equal(typeBreakdown([entry('2026-01-01', 'org', null)])[0].label, 'Ohne Typ');
});


test('stacked years keep the given group order and fill empty years', () => {
  const docs = [entry('2024-01-01', 'a'), entry('2024-02-01', 'b'), entry('2026-01-01', 'a'), entry('2026-01-02', 'x')];
  const years = stackedYearlyCounts(docs, (e) => e.correspondent_id, ['a', 'b'], { now: new Date('2026-06-01T00:00:00') });
  assert.deepEqual(years.map((y) => y.year), [2022, 2023, 2024, 2025, 2026]);
  assert.deepEqual(years.find((y) => y.year === 2024).segments, [{ key: 'a', count: 1 }, { key: 'b', count: 1 }]);
  assert.equal(years.find((y) => y.year === 2026).total, 1, 'unknown groups are skipped');
});

test('collectionMemberSummaries groups by member, counts persons at their organisation', () => {
  const act = [
    { document_date: '2003-05-01', correspondent_id: 'schoolA', document_type: 'Zeugnis', document_id: 'd1' },
    { document_date: '2004-05-01', correspondent_id: 'teacher', document_type: 'Brief', document_id: 'd2' },
    { document_date: '2005-05-01', correspondent_id: 'schoolA', document_type: 'Zeugnis', document_id: 'd3' },
    { document_date: '2006-01-01', correspondent_id: 'schoolA', document_type: 'Zeugnis', document_id: 'd4' },
    { document_date: '2010-01-01', correspondent_id: 'coll', document_type: null, document_id: 'd5' },
    { document_date: '2011-01-01', correspondent_id: 'schoolB', document_type: 'Anmeldung', document_id: 'd6' },
  ];
  const members = [
    { id: 'schoolB', name: 'B', kind: 'organization' },
    { id: 'schoolA', name: 'A', kind: 'organization' },
  ];
  const { rows, direct } = collectionMemberSummaries(act, members, {
    ownId: 'coll',
    parentOf: (id) => (id === 'teacher' ? 'schoolA' : null),
    years: yearRange(2003, 2011),
  });
  assert.deepEqual(rows.map((r) => r.id), ['schoolA', 'schoolB']);
  const a = rows[0];
  assert.equal(a.count, 4);
  assert.deepEqual(a.coverIds, ['d4', 'd3', 'd2']);
  assert.equal(a.years.length, 9);
  assert.equal(a.years.find((y) => y.year === 2005).count, 1);
  assert.equal(direct.count, 1);
  assert.deepEqual(direct.coverIds, ['d5']);
});

test('yearRange is inclusive and capped to the latest years', () => {
  assert.deepEqual(yearRange(2002, 2004), [2002, 2003, 2004]);
  assert.equal(yearRange(1990, 2019, 10)[0], 2010);
  assert.deepEqual(yearRange('', 2019), [2019]);
});
