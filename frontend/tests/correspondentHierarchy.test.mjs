import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildCorrespondentTree,
  canAssignToParent,
  connectionCandidates,
  connectionKindOptions,
  connectionRoleLabel,
  connectionRoleOptions,
  CORRESPONDENT_CONNECTION_ROLES,
  filterCorrespondentTree,
  formatCorrespondent,
  groupCorrespondentTree,
  matchesCorrespondentActivity,
  memberSummaryLabel,
  sortCorrespondentTree,
} from '../src/utils/correspondentHierarchy.js';

const org = { id: 'o1', name: 'Autohaus Müller', kind: 'organization', usage_count: 1, last_document_date: '2026-08-21' };
const torge = { id: 'p1', name: 'Torge Quitsch', kind: 'person', parent_id: 'o1', parent_name: 'Autohaus Müller', usage_count: 2, last_document_date: '2026-09-30' };
const anja = { id: 'p2', name: 'Anja Brandt', kind: 'person', parent_id: 'o1', usage_count: 0 };
const fa = { id: 'o2', name: 'Finanzamt Kiel', kind: 'organization', usage_count: 4 };
const loose = { id: 'u1', name: 'Werkstatt Nord', kind: null, usage_count: 3 };
const collection = { id: 'c1', name: 'Werkstätten', kind: 'collection' };
const all = [torge, fa, loose, anja, org];
const findById = (id) => all.find((c) => c.id === id) || null;

test('formats persons as "Organisation · Person" and others by name', () => {
  assert.equal(formatCorrespondent(torge).label, 'Autohaus Müller · Torge Quitsch');
  assert.equal(formatCorrespondent(anja, findById).label, 'Autohaus Müller · Anja Brandt');
  assert.equal(formatCorrespondent(anja).label, 'Anja Brandt');
  assert.deepEqual(formatCorrespondent(org), { label: 'Autohaus Müller', organization: '', person: '', name: 'Autohaus Müller' });
});

test('tree nests persons under their organization and rolls up counts', () => {
  const tree = buildCorrespondentTree(all);
  assert.deepEqual(tree.map((n) => n.name), ['Autohaus Müller', 'Finanzamt Kiel', 'Werkstatt Nord']);
  const müller = tree[0];
  assert.deepEqual(müller.members.map((m) => m.name), ['Anja Brandt', 'Torge Quitsch']);
  assert.equal(müller.own_count, 1);
  assert.equal(müller.total_count, 3);
  assert.equal(müller.last_activity, '2026-09-30');
});

test('persons whose organization is missing stay visible on top level', () => {
  const tree = buildCorrespondentTree([torge, fa]);
  assert.deepEqual(tree.map((n) => n.name), ['Finanzamt Kiel', 'Torge Quitsch']);
});

test('filter by kind keeps the organization as context for matching persons', () => {
  const tree = buildCorrespondentTree(all);
  const persons = filterCorrespondentTree(tree, { kind: 'person' });
  assert.equal(persons.length, 1);
  assert.equal(persons[0].context_only, true);
  assert.equal(persons[0].members.length, 2);

  const untyped = filterCorrespondentTree(tree, { kind: 'untyped' });
  assert.deepEqual(untyped.map((n) => n.name), ['Werkstatt Nord']);

  const search = filterCorrespondentTree(tree, { query: 'torge' });
  assert.deepEqual(search.map((n) => [n.name, n.members.map((m) => m.name)]), [['Autohaus Müller', ['Torge Quitsch']]]);
});

test('persons join organizations or collections, organizations join collections', () => {
  const school = { id: 'c1', kind: 'collection' };
  assert.equal(canAssignToParent(loose, org), false, 'choose a type before assigning');
  assert.equal(canAssignToParent(loose, school), false);
  assert.equal(canAssignToParent(anja, fa), true);
  assert.equal(canAssignToParent(anja, org), false, 'already assigned');
  assert.equal(canAssignToParent(fa, org), false, 'organizations do not nest in organizations');
  assert.equal(canAssignToParent(fa, school), true, 'organization into a collection');
  assert.equal(canAssignToParent(torge, school), true, 'person directly into a collection');
  assert.equal(canAssignToParent(school, { id: 'c2', kind: 'collection' }), false, 'collections stay on top');
  assert.equal(canAssignToParent(loose, torge), false, 'target must be an organization or collection');
  assert.equal(canAssignToParent(org, org), false);
});

test('collections nest organizations and their persons on three levels', () => {
  const schule = { id: 'c1', name: 'Schule', kind: 'collection', usage_count: 2, last_document_date: '2025-01-01' };
  const a = { id: 's1', name: 'Schule A', kind: 'organization', parent_id: 'c1', usage_count: 5, last_document_date: '2026-02-01' };
  const b = { id: 's2', name: 'Schule B', kind: 'organization', parent_id: 'c1', usage_count: 1 };
  const teacher = { id: 'p9', name: 'Frau Jensen', kind: 'person', parent_id: 's2', usage_count: 3, last_document_date: '2026-10-01' };
  const list = [teacher, b, a, schule];
  const tree = buildCorrespondentTree(list);
  assert.deepEqual(tree.map((n) => n.name), ['Schule']);
  assert.deepEqual(tree[0].members.map((m) => [m.name, m.total_count]), [['Schule A', 5], ['Schule B', 4]]);
  assert.equal(tree[0].total_count, 11);
  assert.equal(tree[0].last_activity, '2026-10-01');
  assert.equal(memberSummaryLabel(tree[0].members), '2 Organisationen');
  assert.equal(memberSummaryLabel([...tree[0].members, teacher]), '2 Organisationen · 1 Person');

  const search = filterCorrespondentTree(tree, { query: 'jensen' });
  assert.deepEqual(search.map((n) => [n.name, n.context_only, n.members.map((m) => [m.name, m.context_only, m.members.map((x) => x.name)])]), [
    ['Schule', true, [['Schule B', true, ['Frau Jensen']]]],
  ]);
  const sorted = sortCorrespondentTree(tree, 'documents');
  assert.deepEqual(sorted[0].members.map((m) => m.name), ['Schule A', 'Schule B']);

  const byId = (id) => list.find((c) => c.id === id);
  assert.equal(formatCorrespondent(a, byId).label, 'Schule A', 'no collection prefix for organizations');
  assert.equal(formatCorrespondent(teacher, byId).label, 'Schule B · Frau Jensen');
  assert.equal(formatCorrespondent({ ...teacher, parent_id: 'c1' }, byId).label, 'Frau Jensen', 'no prefix for persons in a collection');
});

test('activity filter splits active, dormant and empty correspondents', () => {
  const now = new Date('2026-11-02T12:00:00').getTime();
  const tree = buildCorrespondentTree(all);
  assert.equal(matchesCorrespondentActivity(tree[0], 'active', now), true, 'rolled-up last contact counts');
  assert.equal(matchesCorrespondentActivity(fa, 'dormant', now), true, 'documents without date are dormant');
  assert.equal(matchesCorrespondentActivity(anja, 'empty', now), true);
  assert.equal(matchesCorrespondentActivity(anja, 'dormant', now), false);

  const empty = filterCorrespondentTree(tree, { activity: 'empty', now });
  assert.deepEqual(empty.map((n) => [n.name, n.context_only || false, n.members.map((m) => m.name)]), [
    ['Autohaus Müller', true, ['Anja Brandt']],
  ]);
});

test('sorting applies to organizations and their persons', () => {
  const tree = buildCorrespondentTree(all);
  assert.deepEqual(sortCorrespondentTree(tree, 'documents').map((n) => n.name), ['Finanzamt Kiel', 'Autohaus Müller', 'Werkstatt Nord']);
  const recent = sortCorrespondentTree(tree, 'recent');
  assert.equal(recent[0].name, 'Autohaus Müller');
  assert.deepEqual(recent[0].members.map((m) => m.name), ['Torge Quitsch', 'Anja Brandt']);
});

test('overview is split into kind sections, empty sections are dropped', () => {
  const standalone = { id: 'p3', name: 'Robin Sommer', kind: 'person' };
  const sections = groupCorrespondentTree(buildCorrespondentTree([...all, standalone]));
  assert.deepEqual(sections.map((s) => [s.label, s.count, s.nodes.map((n) => n.name)]), [
    ['Organisationen', 2, ['Autohaus Müller', 'Finanzamt Kiel']],
    ['Personen', 1, ['Robin Sommer']],
    ['Ohne Typ', 1, ['Werkstatt Nord']],
  ]);
});

test('connection roles depend on the kind of correspondent', () => {
  const roles = (c, rel) => connectionRoleOptions(c, rel).map((r) => r.value);
  assert.deepEqual(roles(org), ['parent', 'member', 'predecessor', 'successor', 'acts_for', 'agent']);
  assert.deepEqual(roles(torge), ['parent', 'predecessor', 'successor', 'acts_for', 'agent']);
  assert.ok(!roles(fa, [{ role: 'successor', other_id: 'x' }]).includes('successor'), 'only one successor');
  assert.deepEqual(roles(collection), ['member']);
  assert.deepEqual(roles(collection, [{ role: 'successor', other_id: 'x' }]), ['member']);
  assert.deepEqual(roles(loose), []);
  const member = CORRESPONDENT_CONNECTION_ROLES.find((r) => r.value === 'member');
  assert.equal(connectionRoleLabel(member, org), 'Personen');
  assert.equal(connectionRoleLabel(member, { kind: 'collection' }), 'Enthält');
});

test('connection candidates exclude self, linked ones and invalid hierarchy targets', () => {
  const names = (c, role, rel = [], q = '') => connectionCandidates(c, role, all, rel, q).map((x) => x.name);
  const freePerson = { id: 'p3', name: 'Lea Weber', kind: 'person' };
  assert.deepEqual(connectionCandidates(org, 'member', [...all, freePerson]), [freePerson]);
  assert.deepEqual(names(org, 'member', [], 'Werkstatt Nord'), []);
  assert.deepEqual(names(loose, 'parent'), []);
  assert.deepEqual(names(fa, 'parent'), [], 'organizations only join collections');
  assert.deepEqual(names(collection, 'member'), ['Autohaus Müller', 'Finanzamt Kiel'], 'only typed and unassigned entries');
  for (const role of ['predecessor', 'successor']) {
    assert.deepEqual(names(fa, role), ['Autohaus Müller']);
    assert.deepEqual(names(fa, role, [{ role, other_id: org.id }]), []);
    assert.deepEqual(names(torge, role), ['Anja Brandt']);
  }
  assert.deepEqual(names(fa, 'acts_for', [], 'torge'), ['Torge Quitsch']);
  assert.deepEqual(connectionCandidates(fa, 'acts_for', [loose, collection, org]), [org]);
  assert.deepEqual(connectionCandidates(collection, 'acts_for', [org]), []);
  assert.deepEqual(connectionCandidates(fa, 'parent', [collection]), [collection]);
});

test('connection kinds bundle both directions into one choice', () => {
  const kinds = (c, rel) => connectionKindOptions(c, rel).map((k) => [k.label, k.roles]);
  assert.deepEqual(kinds(org), [
    ['Zugehörigkeit', ['member', 'parent']],
    ['Nachfolge', ['predecessor', 'successor']],
    ['Auftrag', ['acts_for', 'agent']],
  ]);
  assert.deepEqual(kinds(torge)[0], ['Gehört zu', ['parent']]);
  assert.deepEqual(kinds(fa, [{ role: 'successor', other_id: 'x' }])[1], ['Nachfolge', ['predecessor']]);
  assert.deepEqual(kinds(collection), [['Mitglied', ['member']]]);
});

test('name sorting ignores a trailing legal form', () => {
  const tree = ['Vodafone GmbH', 'Volksbank eG', 'Vodafone Kabel', 'Vodafone', 'Allianz SE'].map((name, index) => ({ id: String(index), name, members: [] }));
  assert.deepEqual(sortCorrespondentTree(tree, 'name').map((n) => n.name), ['Allianz SE', 'Vodafone', 'Vodafone GmbH', 'Vodafone Kabel', 'Volksbank eG']);
});
