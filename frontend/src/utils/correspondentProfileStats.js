/**
 * Auswertungen für das Korrespondenten-Profil: Verteilung über Jahre, Monate
 * und Dokumenttypen sowie Rhythmus und Jahreszeit. Grundlage ist
 * profile.activity – ein Eintrag je Dokument ({ document_date,
 * correspondent_id, document_type }), aufsteigend nach Datum.
 */

const DAY_MS = 86_400_000;
const MAX_YEARS = 12;
/** Kürzeste Jahresachse, damit wenige Jahre nicht als breiter Block erscheinen. */
const MIN_YEARS = 5;
/** Lücke, ab der eine neue Phase beginnt (Rhythmus „seit …“). */
const PHASE_GAP_DAYS = 365;

export const MONTH_INITIALS = Object.freeze(['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']);

function toDate(iso) {
  if (!iso) return null;
  const d = new Date(String(iso).length <= 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

function datesOf(activity) {
  return (Array.isArray(activity) ? activity : [])
    .map((entry) => toDate(entry?.document_date))
    .filter(Boolean)
    .sort((a, b) => a - b);
}

/**
 * Dokumente je Jahr vom ersten bis zum aktuellen Jahr (mindestens fünf,
 * höchstens zwölf Jahre), getrennt nach direkt und über Personen.
 */
export function yearlyCounts(activity, ownId, { now = new Date() } = {}) {
  const byYear = new Map();
  for (const entry of activity || []) {
    const d = toDate(entry?.document_date);
    if (!d) continue;
    const year = d.getFullYear();
    const bucket = byYear.get(year) || { own: 0, members: 0 };
    if (entry.correspondent_id === ownId) bucket.own += 1;
    else bucket.members += 1;
    byYear.set(year, bucket);
  }
  if (!byYear.size) return [];
  const last = Math.max(now.getFullYear(), ...byYear.keys());
  const first = Math.max(Math.min(Math.min(...byYear.keys()), last - MIN_YEARS + 1), last - MAX_YEARS + 1);
  const years = [];
  for (let year = first; year <= last; year += 1) {
    const { own, members } = byYear.get(year) || { own: 0, members: 0 };
    years.push({ year, own, members, total: own + members });
  }
  return years;
}

/** Dokumente je Kalendermonat (Index 0 = Januar) über alle Jahre. */
export function monthlyCounts(activity) {
  const months = Array(12).fill(0);
  for (const d of datesOf(activity)) months[d.getMonth()] += 1;
  return months;
}

const SEASONS = [
  { label: 'Winter', months: [11, 0, 1] },
  { label: 'Frühjahr', months: [2, 3, 4] },
  { label: 'Sommer', months: [5, 6, 7] },
  { label: 'Herbst', months: [8, 9, 10] },
];

/**
 * Kurzbeschreibung der Jahreszeit-Verteilung („Häufung Frühjahr und Herbst“).
 * Eine Jahreszeit gilt als gehäuft, wenn sie mindestens das 1,5-Fache des
 * Durchschnitts erreicht. Bei weniger als vier Dokumenten keine Aussage.
 */
export function seasonLabel(months) {
  const total = (months || []).reduce((sum, n) => sum + n, 0);
  if (total < 4) return '';
  const average = total / SEASONS.length;
  const peaks = SEASONS
    .map((season) => ({ ...season, count: season.months.reduce((sum, m) => sum + (months[m] || 0), 0) }))
    .filter((season) => season.count >= average * 1.5)
    .map((season) => season.label);
  if (!peaks.length) return 'übers Jahr verteilt';
  if (peaks.length === 1) return `Häufung im ${peaks[0]}`;
  return `Häufung ${peaks.slice(0, -1).join(', ')} und ${peaks.at(-1)}`;
}

function median(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function intervalLabel(days) {
  if (days < 1.5) return 'täglich';
  if (days < 12) return `alle ${Math.round(days)} Tage`;
  if (days < 25) {
    const weeks = Math.round(days / 7);
    return weeks <= 1 ? 'wöchentlich' : `alle ${weeks} Wochen`;
  }
  if (days < 548) {
    const months = Math.round(days / 30.4);
    return months <= 1 ? 'monatlich' : `alle ${months} Mon.`;
  }
  const years = Math.round(days / 365);
  return years <= 1 ? 'jährlich' : `alle ${years} Jahre`;
}

/**
 * Typischer Abstand zwischen zwei Dokumenten (Median) in der jüngsten Phase.
 * Eine Phase endet an einer Lücke von über einem Jahr; lag davor schon etwas,
 * heißt es „seit 2024 · vorher selten“. Ab drei Dokumenten.
 */
export function documentRhythm(activity) {
  const dates = datesOf(activity);
  if (dates.length < 3) return null;
  let start = dates.length - 1;
  while (start > 0 && (dates[start] - dates[start - 1]) / DAY_MS <= PHASE_GAP_DAYS) start -= 1;
  const phase = dates.slice(start);
  // Zu kurze Phase: über den Gesamtzeitraum messen.
  const basis = phase.length >= 3 ? phase : dates;
  const gaps = [];
  for (let i = 1; i < basis.length; i += 1) gaps.push((basis[i] - basis[i - 1]) / DAY_MS);
  const sinceYear = basis[0].getFullYear();
  const hadEarlier = basis !== dates && start > 0;
  return {
    days: median(gaps),
    label: intervalLabel(median(gaps)),
    detail: hadEarlier ? `seit ${sinceYear} · vorher selten` : `gleichmäßig seit ${sinceYear}`,
  };
}

/** Dokumente nach Typ, absteigend; Rest ab `limit` als „Weitere“ zusammengefasst. */
export function typeBreakdown(activity, { limit = 6 } = {}) {
  const counts = new Map();
  for (const entry of activity || []) {
    const name = String(entry?.document_type || '').trim() || 'Ohne Typ';
    counts.set(name, (counts.get(name) || 0) + 1);
  }
  const rows = [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, 'de-DE'));
  if (rows.length <= limit) return rows;
  const rest = rows.slice(limit - 1).reduce((sum, row) => sum + row.count, 0);
  return [...rows.slice(0, limit - 1), { label: 'Weitere', count: rest, isRest: true }];
}

/**
 * Dokumente je Jahr, gestapelt nach Gruppen. `keyOf(entry)` ordnet jedem
 * Dokument eine Gruppe zu; `keys` legt Reihenfolge (unten → oben) fest.
 * Jahresachse wie yearlyCounts.
 */
export function stackedYearlyCounts(activity, keyOf, keys, { now = new Date() } = {}) {
  const byYear = new Map();
  for (const entry of activity || []) {
    const d = toDate(entry?.document_date);
    if (!d) continue;
    const key = keyOf(entry);
    if (!keys.includes(key)) continue;
    const year = d.getFullYear();
    const bucket = byYear.get(year) || Object.fromEntries(keys.map((k) => [k, 0]));
    bucket[key] += 1;
    byYear.set(year, bucket);
  }
  if (!byYear.size) return [];
  const last = Math.max(now.getFullYear(), ...byYear.keys());
  const first = Math.max(Math.min(Math.min(...byYear.keys()), last - MIN_YEARS + 1), last - MAX_YEARS + 1);
  const years = [];
  for (let year = first; year <= last; year += 1) {
    const bucket = byYear.get(year) || Object.fromEntries(keys.map((k) => [k, 0]));
    const segments = keys.map((key) => ({ key, count: bucket[key] }));
    years.push({ year, segments, total: segments.reduce((sum, s) => sum + s.count, 0) });
  }
  return years;
}

/**
 * Kacheln einer Sammlung: je direktem Mitglied (Personen zählen bei ihrer
 * Organisation) Anzahl, Zeitraum, häufigste Dokumenttypen, die neuesten
 * Dokument-IDs als Deckblätter und eine Jahresreihe über `years`.
 * Dokumente der Sammlung selbst bilden den Eintrag `direct`.
 */
export function collectionMemberSummaries(activity, members, {
  ownId, parentOf = () => null, years = [], coverLimit = 3,
} = {}) {
  const memberIds = new Set((members || []).map((m) => m.id));
  const groups = new Map((members || []).map((m) => [m.id, []]));
  const directEntries = [];
  for (const entry of activity || []) {
    const d = toDate(entry?.document_date);
    if (!d) continue;
    const cid = entry.correspondent_id;
    if (cid === ownId) { directEntries.push({ ...entry, date: d }); continue; }
    const memberId = memberIds.has(cid) ? cid : parentOf(cid);
    if (groups.has(memberId)) groups.get(memberId).push({ ...entry, date: d });
  }
  const summarize = (entries) => {
    const sorted = entries.slice().sort((a, b) => a.date - b.date);
    const perYear = new Map();
    for (const e of sorted) {
      const y = e.date.getFullYear();
      perYear.set(y, (perYear.get(y) || 0) + 1);
    }
    return {
      count: sorted.length,
      first: sorted[0]?.date || null,
      last: sorted.at(-1)?.date || null,
      coverIds: sorted.filter((e) => e.document_id).slice(-coverLimit).reverse().map((e) => e.document_id),
      years: years.map((year) => ({ year, count: perYear.get(year) || 0 })),
    };
  };
  const rows = (members || []).map((m) => ({ id: m.id, name: m.name, kind: m.kind, ...summarize(groups.get(m.id)) }));
  rows.sort((a, b) => (a.first && b.first ? a.first - b.first : a.first ? -1 : b.first ? 1 : a.name.localeCompare(b.name, 'de-DE')));
  return { rows, direct: summarize(directEntries) };
}

/** Jahre von `start` bis `end` (inklusive), höchstens `max` (die jüngsten). */
export function yearRange(start, end, max = 24) {
  const a = Number(start);
  const b = Number(end);
  if (!a || !b || b < a) return a ? [a] : b ? [b] : [];
  const from = Math.max(a, b - max + 1);
  return Array.from({ length: b - from + 1 }, (_, i) => from + i);
}

/** Deckkraft-Stufen der Mitgliedsfarbe (Anteil der Akzentfarbe in %). */
export const COLLECTION_TONE_STRENGTHS = Object.freeze([100, 74, 54, 38, 26]);

/** Farbe des n-ten Mitglieds einer Sammlung: Abstufung der Akzentfarbe. */
export function collectionTone(index) {
  const strength = COLLECTION_TONE_STRENGTHS[index % COLLECTION_TONE_STRENGTHS.length];
  return `color-mix(in srgb, var(--pm-accent) ${strength}%, var(--pm-app-surface))`;
}
