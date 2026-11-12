/**
 * Hierarchie der Korrespondenten: Sammlung → Organisation → Person (höchstens
 * drei Ebenen; Personen können auch direkt in einer Sammlung liegen).
 *
 * Einzige Stelle, die festlegt, wie Organisation und Person zusammen angezeigt
 * werden („Organisation · Person“) und wie die Übersicht gruppiert wird. Alle
 * Oberflächen (Liste, Detail, Filter, Übersicht) nutzen diese Helfer, statt
 * Namen selbst zusammenzusetzen.
 */

import { stripLegalForm } from './legalForms.js';

export const CORRESPONDENT_KIND_META = Object.freeze({
  organization: { label: 'Organisation', icon: 'mdi-domain' },
  person: { label: 'Person', icon: 'mdi-account-outline' },
  collection: { label: 'Sammlung', icon: 'mdi-shape-outline' },
});

export function correspondentKindIcon(kind) {
  return CORRESPONDENT_KIND_META[kind]?.icon || null;
}

export function correspondentKindLabel(kind) {
  return CORRESPONDENT_KIND_META[kind]?.label || 'Ohne Typ';
}

const collator = new Intl.Collator('de-DE', { sensitivity: 'base', numeric: true });
// „Vodafone GmbH“ steht unter V neben „Vodafone“: sortiert wird nach dem Namen ohne Rechtsform.
const sortName = (c) => stripLegalForm(c?.name || '');
const byName = (a, b) => collator.compare(sortName(a), sortName(b)) || collator.compare(String(a?.name || ''), String(b?.name || ''));

/**
 * Angezeigter Name: Kurzname, falls vorhanden. Sammlungen haben keinen.
 */
export function correspondentDisplayName(correspondent) {
  const shortName = correspondent?.kind === 'collection' ? '' : String(correspondent?.short_name || '').trim();
  return shortName || String(correspondent?.name || '').trim();
}

/** Anzeigename des übergeordneten Eintrags, sonst ''. */
export function correspondentParentName(correspondent, findById = null) {
  if (!correspondent?.parent_id) return '';
  return correspondentDisplayName(findById?.(correspondent.parent_id) ?? {
    name: correspondent.parent_name,
    short_name: correspondent.parent_short_name,
  });
}

/**
 * Anzeige „Organisation · Person“. Ohne Organisation nur der eigene Name.
 * Liefert zusätzlich die Teile, damit Oberflächen die Person abgesetzt zeigen
 * können.
 */
export function formatCorrespondent(correspondent, findById = null) {
  const name = correspondentDisplayName(correspondent);
  // Nur Personen tragen ihre Organisation im Namen; eine Sammlung ist
  // Gruppierung und kein Absender („Schule A“, nicht „Schule · Schule A“).
  const parentKind = correspondent?.parent_id ? findById?.(correspondent.parent_id)?.kind : null;
  const organization = correspondent?.kind === 'person' && parentKind !== 'collection'
    ? correspondentParentName(correspondent, findById)
    : '';
  if (!organization) return { label: name, organization: '', person: '', name };
  return { label: `${organization} · ${name}`, organization, person: name, name };
}

/**
 * Baut die Übersicht: oberste Einträge mit ihren Mitgliedern (je A–Z) –
 * Sammlungen mit Organisationen/Personen, Organisationen mit Personen.
 * Einträge, deren übergeordneter Eintrag nicht (mehr) in der Liste ist,
 * erscheinen eigenständig. total_count = eigene Dokumente + die aller
 * Mitglieder (rekursiv), last_activity entsprechend.
 */
export function buildCorrespondentTree(correspondents = []) {
  const items = Array.isArray(correspondents) ? correspondents.filter((c) => c?.id) : [];
  const ids = new Set(items.map((c) => c.id));
  const membersByParent = new Map();
  for (const item of items) {
    if (!item.parent_id || !ids.has(item.parent_id)) continue;
    if (!membersByParent.has(item.parent_id)) membersByParent.set(item.parent_id, []);
    membersByParent.get(item.parent_id).push(item);
  }
  const toNode = (item, depth) => {
    // Schutz vor fehlerhaften Daten (Zyklen): höchstens drei Ebenen.
    const members = depth < 2 ? (membersByParent.get(item.id) || []).map((m) => toNode(m, depth + 1)).sort(byName) : [];
    const ownCount = Number(item.usage_count || 0);
    const lastDates = [item.last_document_date, ...members.map((m) => m.last_activity)].filter(Boolean);
    return {
      ...item,
      members,
      own_count: ownCount,
      total_count: ownCount + members.reduce((sum, m) => sum + m.total_count, 0),
      last_activity: lastDates.length ? lastDates.sort().at(-1) : null,
    };
  };
  return items
    .filter((item) => !item.parent_id || !ids.has(item.parent_id))
    .map((item) => toNode(item, 0))
    .sort(byName);
}

/** Alle Mitglieder eines Knotens rekursiv (ohne den Knoten selbst). */
export function correspondentDescendants(node) {
  return (node?.members || []).flatMap((m) => [m, ...correspondentDescendants(m)]);
}

/** „3 Organisationen“, „1 Person“, „2 Organisationen · 1 Person“ für die direkten Mitglieder. */
export function memberSummaryLabel(members = []) {
  const orgs = members.filter((m) => m.kind === 'organization').length;
  const persons = members.length - orgs;
  const parts = [];
  if (orgs) parts.push(`${orgs} ${orgs === 1 ? 'Organisation' : 'Organisationen'}`);
  if (persons) parts.push(`${persons} ${persons === 1 ? 'Person' : 'Personen'}`);
  return parts.join(' · ');
}

const DAY_MS = 86_400_000;
const ACTIVE_WINDOW_DAYS = 365;

/** Letzter Kontakt (eigenes Dokument bzw. bei Organisationen inkl. Personen). */
const lastActivityOf = (c) => c?.last_activity ?? c?.last_document_date ?? null;
const documentCountOf = (c) => Number(c?.total_count ?? c?.usage_count ?? 0);

/**
 * Aktivitätsfilter: all | active (Kontakt in den letzten 12 Monaten) |
 * dormant (Dokumente vorhanden, aber länger still) | empty (ohne Dokumente).
 */
export function matchesCorrespondentActivity(correspondent, activity = 'all', now = Date.now()) {
  if (activity === 'all') return true;
  const count = documentCountOf(correspondent);
  if (activity === 'empty') return count === 0;
  if (!count) return false;
  const last = lastActivityOf(correspondent);
  const time = last ? new Date(String(last).length <= 10 ? `${last}T00:00:00` : last).getTime() : NaN;
  const recent = Number.isFinite(time) && now - time <= ACTIVE_WINDOW_DAYS * DAY_MS;
  return activity === 'active' ? recent : !recent;
}

/**
 * Filter der Übersicht. kind: all | organization | person | untyped;
 * activity siehe matchesCorrespondentActivity. Organisationen, die nur über
 * passende Personen erscheinen, bleiben als Kontext (context_only) stehen.
 */
const normalizeSearch = (value) => String(value ?? '').trim().replace(/\s+/g, ' ').toLocaleLowerCase('de-DE');

/**
 * Alle Schreibweisen, unter denen ein Korrespondent gesucht werden kann: Name,
 * Kurzname (Sammlungen haben keinen) und – je nach Einstellung – Aliase.
 */
export function correspondentSearchValues(correspondent, { aliases = true } = {}) {
  if (!correspondent) return [];
  return [
    correspondent.name,
    correspondent.kind === 'collection' ? null : correspondent.short_name,
    ...(aliases ? (correspondent.aliases || []).map((alias) => (typeof alias === 'string' ? alias : alias?.alias)) : []),
  ].filter(Boolean);
}

/** Eine Suche für alle Listen, Dialoge und Menüs mit Korrespondenten. */
export function matchesCorrespondentQuery(correspondent, query, { aliases = true, extra = [] } = {}) {
  const needle = normalizeSearch(query);
  if (!needle) return true;
  return [...correspondentSearchValues(correspondent, { aliases }), ...extra].some((value) => normalizeSearch(value).includes(needle));
}

export function filterCorrespondentTree(tree, { kind = 'all', query = '', activity = 'all', now = Date.now(), searchAliases = true } = {}) {
  const needle = normalizeSearch(query);
  const matchesQuery = (c) => matchesCorrespondentQuery(c, needle, { aliases: searchAliases });
  const matchesKind = (c) => {
    if (kind === 'all') return true;
    if (kind === 'untyped') return !c?.kind;
    return c?.kind === kind;
  };
  const matches = (c) => matchesKind(c) && matchesQuery(c) && matchesCorrespondentActivity(c, activity, now);
  const unfiltered = kind === 'all' && !needle && activity === 'all';
  const filterNode = (node) => {
    const members = (node.members || []).map(filterNode).filter(Boolean);
    // Ohne Filter alle Mitglieder zeigen, sonst nur die passenden.
    if (matches(node)) return { ...node, members: unfiltered ? node.members : members };
    return members.length ? { ...node, members, context_only: true } : null;
  };
  return tree.map(filterNode).filter(Boolean);
}

export const CORRESPONDENT_SORT_OPTIONS = Object.freeze([
  { value: 'name', label: 'Name A–Z' },
  { value: 'documents', label: 'Meiste Dokumente' },
  { value: 'recent', label: 'Letzter Kontakt' },
]);

/** Sortiert alle Ebenen nach demselben Schlüssel; nach Namen so, wie er angezeigt wird. */
export function sortCorrespondentTree(tree, sort = 'name') {
  const byLabel = (a, b) => collator.compare(
    stripLegalForm(correspondentDisplayName(a)), stripLegalForm(correspondentDisplayName(b))
  ) || byName(a, b);
  const compare = {
    documents: (a, b) => documentCountOf(b) - documentCountOf(a) || byLabel(a, b),
    recent: (a, b) => String(lastActivityOf(b) || '').localeCompare(String(lastActivityOf(a) || '')) || byLabel(a, b),
  }[sort] || byLabel;
  const sortNodes = (nodes) => nodes.map((node) => ({ ...node, members: sortNodes(node.members || []) })).sort(compare);
  return sortNodes(tree);
}

export const CORRESPONDENT_SECTIONS = Object.freeze([
  { key: 'collection', label: 'Sammlungen' },
  { key: 'organization', label: 'Organisationen' },
  { key: 'person', label: 'Personen' },
  { key: 'untyped', label: 'Ohne Typ' },
]);

/**
 * Teilt die (gefilterte, sortierte) Übersicht in Abschnitte nach Typ; die
 * Reihenfolge innerhalb bleibt erhalten, leere Abschnitte entfallen.
 * count = Einträge des Abschnitts ohne die eingerückten Personen.
 */
export function groupCorrespondentTree(tree = []) {
  const byKey = new Map(CORRESPONDENT_SECTIONS.map((s) => [s.key, []]));
  for (const node of tree) {
    const key = byKey.has(node?.kind) ? node.kind : 'untyped';
    byKey.get(key).push(node);
  }
  return CORRESPONDENT_SECTIONS
    .map((section) => ({ ...section, nodes: byKey.get(section.key), count: byKey.get(section.key).length }))
    .filter((section) => section.count > 0);
}

/**
 * Personen können zu Organisationen oder Sammlungen gehören,
 * Organisationen nur zu Sammlungen.
 */
export function canAssignToParent(child, parent) {
  if (!child?.id || !parent?.id || child.id === parent.id) return false;
  if (child.parent_id === parent.id) return false;
  if (child.kind === 'person') return parent.kind === 'organization' || parent.kind === 'collection';
  return child.kind === 'organization' && parent.kind === 'collection';
}

/**
 * Arten einer Verbindung aus Sicht des Profils (Rolle des Gegenübers).
 * parent/person nutzen die Hierarchie (parent_id), die übrigen die
 * gespeicherten Verbindungen (Nachfolger, handelt für).
 */
export const CORRESPONDENT_CONNECTION_ROLES = Object.freeze([
  { value: 'parent', label: 'Gehört zu', icon: 'mdi-domain', hint: (n) => `${n} gehört zu …` },
  {
    value: 'member',
    label: 'Enthält',
    icon: 'mdi-account-outline',
    hint: (n, kind) => (kind === 'collection' ? `Mitglied von ${n}` : `Person bei ${n}`),
  },
  { value: 'predecessor', label: 'Vorgänger', icon: 'mdi-history', hint: (n) => `Früherer Name von ${n}` },
  { value: 'successor', label: 'Nachfolger', icon: 'mdi-arrow-right', hint: (n) => `${n} heißt heute …` },
  { value: 'acts_for', label: 'Handelt für', icon: 'mdi-briefcase-outline', hint: (n) => `${n} handelt im Auftrag von …` },
  { value: 'agent', label: 'Vertreten durch', icon: 'mdi-account-tie-outline', hint: (n) => `… handelt im Auftrag von ${n}` },
]);

/** Zeilenbeschriftung im Profil: Mitglieder einer Organisation heißen „Personen“. */
export function connectionRoleLabel(role, correspondent) {
  if (role?.value === 'member' && correspondent?.kind === 'organization') return 'Personen';
  return role?.label || '';
}

/** Arten fürs Anlegen: je Art eine Pille, die Richtung wählt der Satz darunter. */
const CONNECTION_KINDS = [
  { value: 'membership', roles: ['member', 'parent'] },
  { value: 'succession', label: 'Nachfolge', roles: ['predecessor', 'successor'] },
  { value: 'mandate', label: 'Auftrag', roles: ['acts_for', 'agent'] },
];

const supportsSemanticConnections = (kind) => kind === 'organization' || kind === 'person';

/** Welche Verbindungen sich für `correspondent` neu anlegen lassen. */
export function connectionRoleOptions(correspondent, relations = []) {
  if (!correspondent?.id || !correspondent.kind) return [];
  const kind = correspondent.kind;
  const hasSuccessor = relations.some((r) => r.role === 'successor');
  return CORRESPONDENT_CONNECTION_ROLES.filter((role) => {
    if (role.value === 'parent') return kind !== 'collection';
    if (role.value === 'member') return kind === 'organization' || kind === 'collection';
    return supportsSemanticConnections(kind) && (role.value !== 'successor' || !hasSuccessor);
  });
}

/** Verfügbare Arten mit ihren (in dieser Lage möglichen) Rollen. */
export function connectionKindOptions(correspondent, relations = []) {
  const available = new Set(connectionRoleOptions(correspondent, relations).map((r) => r.value));
  const membershipLabel = (roles) => {
    if (roles.length > 1) return 'Zugehörigkeit';
    if (roles[0] === 'parent') return 'Gehört zu';
    return correspondent?.kind === 'organization' ? 'Person' : 'Mitglied';
  };
  return CONNECTION_KINDS
    .map((kind) => {
      const roles = kind.roles.filter((role) => available.has(role));
      return { value: kind.value, label: kind.label || membershipLabel(roles), roles };
    })
    .filter((kind) => kind.roles.length);
}

/** Mögliche Gegenüber für eine Rolle; bereits verbundene und man selbst entfallen. */
export function connectionCandidates(correspondent, role, all = [], relations = [], query = '') {
  if (!connectionRoleOptions(correspondent, relations).some((option) => option.value === role)) return [];
  const needle = String(query || '').trim().toLocaleLowerCase('de-DE');
  const linked = new Set(relations.filter((r) => r.role === role).map((r) => r.other_id));
  return all
    .filter((c) => c?.id && c.id !== correspondent.id && !linked.has(c.id))
    .filter((c) => {
      if (role === 'parent') return canAssignToParent(correspondent, c);
      // Nur freie Einträge: Umhängen aus einer anderen Zugehörigkeit geschieht
      // bewusst im Profil des Eintrags selbst.
      if (role === 'member') {
        return !c.parent_id && canAssignToParent(c, correspondent);
      }
      if (role === 'predecessor' || role === 'successor') return c.kind === correspondent.kind;
      return supportsSemanticConnections(c.kind);
    })
    .filter((c) => !needle || matchesCorrespondentQuery(c, needle))
    .sort(byName);
}
