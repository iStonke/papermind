export const SPEECH_ENGINE_NAMES = { piper: 'Piper', kokoro: 'Thorsten Kokoro', cosyvoice: 'Thorsten CosyVoice' };
export const SPEECH_VOICES = [
  { value: 'standard', label: 'Klar – Thorsten High' },
  { value: 'neutral', label: 'Sanft – Thorsten Emotional' },
  { value: 'amused', label: 'Heiter – Thorsten Emotional' },
  { value: 'sleepy', label: 'Ruhig – Thorsten Emotional' },
  { value: 'whisper', label: 'Flüstern – Thorsten Emotional' },
];
export const SPEECH_LANGUAGES = [
  { value: 'auto', label: 'Automatisch – Deutsch und Englisch' },
  { value: 'de', label: 'Nur Deutsch' },
  { value: 'en', label: 'Nur Englisch – Ryan High' },
];
export function defaultSpeechOptions() {
  return { engine: 'piper', speed: 1, sentence_pause: 0.18, paragraph_pause: 0.38, normalize_numbers: true, pronunciations: [] };
}
function bounded(value, fallback, minimum, maximum) {
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.min(maximum, Math.max(minimum, value)) : fallback;
}
export function normalizeSpeechOptions(value) {
  const defaults = defaultSpeechOptions();
  const raw = value && typeof value === 'object' ? value : {};
  const sentence = bounded(raw.sentence_pause, defaults.sentence_pause, 0.05, 0.8);
  const seen = new Set();
  const pronunciations = (Array.isArray(raw.pronunciations) ? raw.pronunciations : []).flatMap((entry) => {
    const word = String(entry?.word || '').trim();
    const pronunciation = String(entry?.pronunciation || '').trim();
    const caseSensitive = entry?.case_sensitive === true;
    const key = (caseSensitive ? word : word.toLocaleLowerCase('de-DE')) + ':' + caseSensitive;
    if (!word || !pronunciation || word.length > 120 || pronunciation.length > 300 ||
        /[\r\n\0]/.test(word + pronunciation) || seen.has(key)) return [];
    seen.add(key);
    return [{ word, pronunciation, case_sensitive: caseSensitive, enabled: entry?.enabled !== false }];
  }).slice(0, 100);
  return {
    engine: Object.hasOwn(SPEECH_ENGINE_NAMES, raw.engine) ? raw.engine : defaults.engine,
    speed: bounded(raw.speed, defaults.speed, 0.6, 1.5),
    sentence_pause: sentence,
    paragraph_pause: Math.max(sentence, bounded(raw.paragraph_pause, defaults.paragraph_pause, 0.1, 1.8)),
    normalize_numbers: typeof raw.normalize_numbers === 'boolean' ? raw.normalize_numbers : true,
    pronunciations,
  };
}
