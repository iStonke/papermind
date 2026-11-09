// Rechtsformen in Korrespondentennamen – Spiegel von backend/app/services/legal_forms.py.
// Beide Seiten prüfen gegen backend/tests/fixtures/legal_forms.json.
// Abgetrennt wird nur am Namensende und nur, wenn davor noch ein Name steht.

const DOT = String.raw`\.?`;
const SP = String.raw`\s*`;
const AND = String.raw`\s*(?:&|\+|und)\s*`;
const CO = String.raw`Co${DOT}`;
const UG = String.raw`UG${SP}\(\s*haftungsbeschr(?:ä|ae|a)nkt\s*\)`;
const GMBH = 'GmbH';

// [kanonisch, Muster, Groß-/Kleinschreibung egal]
const FORMS = [
  ['GmbH & Co. KGaA', `${GMBH}${AND}${CO}${SP}KGaA`, true],
  ['GmbH & Co. KG', `${GMBH}${AND}${CO}${SP}KG`, true],
  ['UG (haftungsbeschränkt) & Co. KG', `${UG}${AND}${CO}${SP}KG`, true],
  ['AG & Co. KGaA', `AG${AND}${CO}${SP}KGaA`, true],
  ['AG & Co. KG', `AG${AND}${CO}${SP}KG`, true],
  ['SE & Co. KGaA', `SE${AND}${CO}${SP}KGaA`, true],
  ['SE & Co. KG', `SE${AND}${CO}${SP}KG`, true],
  ['& Co. KG', String.raw`(?:&|\+|und)${SP}${CO}${SP}KG`, true],
  ['PartG mbB', `PartG${SP}mbB`, true],
  ['UG (haftungsbeschränkt)', UG, true],
  ['gGmbH', 'gGmbH', false],
  ['GmbH', GMBH, true],
  ['mbH', 'mbH', false],
  ['KGaA', 'KGaA', true],
  ['VVaG', 'VVaG', true],
  ['OHG', 'OHG', true],
  ['GbR', 'GbR', true],
  ['PartG', 'PartG', true],
  ['AöR', 'A(?:ö|oe)R', true],
  ['KdöR', 'Kd(?:ö|oe)R', true],
  ['e.V.', `e${DOT}${SP}V${DOT}`, true],
  ['e.K.', `e${DOT}${SP}K(?:fm|fr|fn)?${DOT}`, true],
  ['eG', 'eG', false],
  ['AG', 'AG', false],
  ['SE', 'SE', false],
  ['KG', 'KG', false],
  ['UG', 'UG', false],
  ['Ltd.', `Ltd${DOT}|Limited`, true],
  ['Inc.', `Inc${DOT}|Incorporated`, true],
  ['LLC', `L${DOT}L${DOT}C${DOT}`, true],
  ['Corp.', `Corp${DOT}|Corporation`, true],
  ['plc', 'plc', true],
  ['B.V.', `B${DOT}${SP}V${DOT}`, false],
  ['N.V.', `N${DOT}${SP}V${DOT}`, false],
  ['S.A.', `S${DOT}${SP}A${DOT}`, false],
  ['S.à r.l.', `S${DOT}${SP}(?:à|a)${SP}r${DOT}${SP}l${DOT}`, true],
  ['S.r.l.', `S${DOT}${SP}r${DOT}${SP}l${DOT}`, true],
  ['SAS', String.raw`S\.?A\.?S\.?`, false],
];

const SUFFIX = FORMS.map(([canonical, pattern, ci]) => [canonical, new RegExp(String.raw`[\s,]+(?:${pattern})[\s.,;:]*$`, ci ? 'iu' : 'u')]);
const ANYWHERE = FORMS.map(([canonical, pattern, ci]) => [canonical, new RegExp(String.raw`(?<![\p{L}\p{N}_])(?:${pattern})(?![\p{L}\p{N}_])`, ci ? 'giu' : 'gu')]);
const TRAILING = /[\s.,;:\-–]+$/u;
const HAS_WORD = /[\p{L}\p{N}]/u;

function clean(value) {
  return String(value ?? '').normalize('NFC').replace(/\s+/gu, ' ').trim();
}

/** Name in Kern und kanonische Rechtsform am Ende zerlegen. */
export function splitLegalForm(value) {
  const text = clean(value);
  let best = null;
  for (const [canonical, pattern] of SUFFIX) {
    const match = pattern.exec(text);
    if (match && (!best || match.index < best.index)) best = { index: match.index, canonical };
  }
  if (!best) return { base: text, legalForm: null };
  const base = text.slice(0, best.index).replace(TRAILING, '').trim();
  if (!HAS_WORD.test(base)) return { base: text, legalForm: null };
  return { base, legalForm: best.canonical };
}

export function stripLegalForm(value) {
  return splitLegalForm(value).base;
}

export function containsLegalForm(value) {
  const text = clean(value);
  return ANYWHERE.some(([, pattern]) => { pattern.lastIndex = 0; return pattern.test(text); });
}

/** Text vor der ersten Rechtsform („Vodafone GmbH Kundenservice" → „Vodafone"). */
export function cutAtLegalForm(value) {
  const text = clean(value);
  let first = null;
  for (const [, pattern] of ANYWHERE) {
    pattern.lastIndex = 0;
    for (const match of text.matchAll(pattern)) {
      const head = text.slice(0, match.index).replace(TRAILING, '').trim();
      if (HAS_WORD.test(head)) {
        if (first === null || match.index < first) first = match.index;
        break;
      }
    }
  }
  return first === null ? text : text.slice(0, first).replace(TRAILING, '').trim();
}

/** Vergleichsschlüssel ohne Rechtsform, Groß-/Kleinschreibung egal. */
export function legalFormKey(value) {
  return stripLegalForm(value).toLocaleLowerCase('de-DE');
}

/** Gleicher Kern und keine widersprüchlichen Rechtsformen. */
export function namesEquivalent(left, right) {
  const a = splitLegalForm(left);
  const b = splitLegalForm(right);
  if (!a.base || a.base.toLocaleLowerCase('de-DE') !== b.base.toLocaleLowerCase('de-DE')) return false;
  return !a.legalForm || !b.legalForm || a.legalForm === b.legalForm;
}

/**
 * Kurzname für eine neue Organisation: ohne Rechtsform, außer sie soll sichtbar bleiben.
 * undefined = keine Rechtsform erkannt (Backend entscheidet), null = bewusst keiner.
 */
export function legalFormShortName(name, keepLegalForm = false) {
  const { base, legalForm } = splitLegalForm(name);
  if (!legalForm) return undefined;
  return keepLegalForm ? null : base.slice(0, 60).trimEnd();
}
