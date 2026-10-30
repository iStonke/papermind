export const relatedFeatures = [
  { key: 'series', label: 'Dokumentserien', description: 'Wiederkehrende Dokumente mit gleichem Titel und passenden Metadaten.' },
  { key: 'title', label: 'Ähnliche Titel', description: 'Gemeinsame aussagekräftige Wörter im Dokumenttitel.' },
  { key: 'tags', label: 'Gemeinsame Tags', description: 'Seltene gemeinsame Tags zählen stärker als häufig verwendete.' },
  { key: 'correspondent', label: 'Korrespondent', description: 'Dokumente desselben Absenders oder Empfängers.' },
  { key: 'type', label: 'Dokumenttyp', description: 'Ein gemeinsamer Typ unterstützt andere Gemeinsamkeiten; allein genügt er nicht.' },
];
const normalWeights = () => Object.fromEntries(relatedFeatures.map(({ key }) => [key, 'normal']));
export const relatedProfiles = [
  { value: 'balanced', label: 'Ausgewogen', description: 'Kombiniert die verfügbaren Gemeinsamkeiten.', weights: normalWeights() },
  { value: 'process', label: 'Gleicher Vorgang', description: 'Bevorzugt Dokumentserien und denselben Korrespondenten.', weights: { ...normalWeights(), series: 'high', tags: 'low', correspondent: 'high' } },
  { value: 'thematic', label: 'Thematisch verwandt', description: 'Betont gemeinsame Tags und ähnliche Titel.', weights: { series: 'low', title: 'high', tags: 'high', correspondent: 'low', type: 'low' } },
];
export function normalizeRelatedPreferences(value) {
  const preset = relatedProfiles.find(profile => profile.value === value?.profile);
  if (preset) return { profile: preset.value, weights: { ...preset.weights } };
  if (value?.profile !== 'custom') return { profile: 'balanced', weights: normalWeights() };
  return { profile: 'custom', weights: Object.fromEntries(relatedFeatures.map(({ key }) =>
    [key, ['low', 'normal', 'high'].includes(value.weights?.[key]) ? value.weights[key] : 'normal'])) };
}
