/*
 * Mock-Datenquelle für M1. Ersetzt in M2/M4/M5 durch echte Stores/APIs
 * (documents, correspondents, dossiers, KI-Chat). Bewusst hier gebündelt,
 * damit die Nodes gegen eine stabile, realistische Oberfläche gebaut werden
 * können, bevor Backend/Reader/Chat angebunden sind.
 */

export const MOCK_DOCUMENTS = [
  {
    id: 'doc-1',
    title: 'Mietvertrag_2024.pdf',
    correspondent: 'Hausverwaltung Renz',
    pages: 6,
    quotePage: 3,
    quote: 'Die Miete erhöht sich jährlich um 3,5 % des jeweiligen Vormonatsbetrags.',
  },
  {
    id: 'doc-2',
    title: 'Nebenkosten_2023.pdf',
    correspondent: 'Hausverwaltung Renz',
    pages: 4,
    quotePage: 2,
    quote: 'Die Vorauszahlungen werden ab dem 01.01. auf 210 € monatlich angepasst.',
  },
  {
    id: 'doc-3',
    title: 'Stromabrechnung_Stadtwerke.pdf',
    correspondent: 'Stadtwerke Musterstadt',
    pages: 2,
    quotePage: 1,
    quote: 'Der Jahresverbrauch beträgt 2.740 kWh; der Abschlag steigt auf 89 € pro Monat.',
  },
  {
    id: 'doc-4',
    title: 'Versicherungspolice_Hausrat.pdf',
    correspondent: 'Allsecur Versicherung',
    pages: 8,
    quotePage: 5,
    quote: 'Die Deckungssumme beträgt 65.000 €; grobe Fahrlässigkeit ist mitversichert.',
  },
];

export const MOCK_CORRESPONDENTS = [
  { id: 'cor-1', name: 'Hausverwaltung Renz', kind: 'organization' },
  { id: 'cor-2', name: 'Stadtwerke Musterstadt', kind: 'organization' },
  { id: 'cor-3', name: 'Allsecur Versicherung', kind: 'organization' },
  { id: 'cor-4', name: 'Dr. Petra Lindqvist', kind: 'person' },
];

export const MOCK_DOSSIERS = [
  { id: 'dos-1', title: 'Objekt Ahornweg' },
  { id: 'dos-2', title: 'Steuer 2024' },
];

/** Verwei­sbare Ziele für [[…]] und /verweis — Dokumente, Personen, Dossiers. */
export function mockLinkTargets() {
  return [
    ...MOCK_DOCUMENTS.map(d => ({ id: d.id, label: d.title, type: 'document', hint: d.correspondent })),
    ...MOCK_CORRESPONDENTS.map(c => ({ id: c.id, label: c.name, type: 'correspondent', hint: c.kind === 'person' ? 'Person' : 'Organisation' })),
    ...MOCK_DOSSIERS.map(d => ({ id: d.id, label: d.title, type: 'dossier', hint: 'Dossier' })),
  ];
}

const TYPE_GLYPH = { document: '▢', correspondent: '◐', dossier: '▤', note: '✎' };
export function targetGlyph(type) { return TYPE_GLYPH[type] || '↗'; }

/**
 * Simulierte KI-Antwort. In M5 ruft dies den echten KI-Chat (api/ai.js) mit
 * Dokumentkontext auf; hier eine plausible, feste Antwort samt Quellen.
 */
export function mockAiAnswer(prompt = '') {
  const q = prompt.trim();
  return {
    prompt: q,
    text: q
      ? `Zu „${q}": Über fünf Jahre summiert sich die Staffel auf rund +18,8 %. Gegenüber der ortsüblichen Vergleichsmiete liegt das im oberen Rahmen — eine Prüfung ist empfehlenswert.`
      : 'Über fünf Jahre summiert sich die Staffel auf rund +18,8 %. Gegenüber der ortsüblichen Vergleichsmiete liegt das im oberen Rahmen — eine Prüfung ist empfehlenswert.',
    sources: [
      { docId: 'doc-1', title: 'Mietvertrag_2024.pdf', page: 3 },
      { docId: 'doc-2', title: 'Nebenkosten_2023.pdf', page: 2 },
    ],
  };
}
