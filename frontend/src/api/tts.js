import { apiGet, authHeaders, getBaseUrl } from './client.js';

const DEFAULT_ERROR = 'Der markierte Text konnte nicht vorgelesen werden.';

async function speechError(response) {
  try {
    const payload = await response.json();
    return new Error(payload?.error?.message || DEFAULT_ERROR);
  } catch {
    return new Error(DEFAULT_ERROR);
  }
}

/** Erzeugt die WAV-Datei und Vergleichsmetriken lokal im PaperMind-Backend. */
export const getSpeechEngines = () => apiGet('/api/tts/engines');

export async function synthesizeSpeechWithMetrics(text, { signal, voice = 'standard', languageMode = 'auto', options } = {}) {
  const response = await fetch(`${getBaseUrl()}/api/tts/speech`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: {
      ...authHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text, voice, language_mode: languageMode, ...(options ? { options } : {}) }),
    signal,
  });
  if (!response.ok) throw await speechError(response);
  const contentType = String(response.headers.get('content-type') || '').toLowerCase();
  if (!contentType.includes('audio/wav')) throw new Error(DEFAULT_ERROR);
  const blob = await response.blob();
  const metric = (header) => {
    const raw = response.headers.get(header);
    const value = Number(raw);
    return raw && Number.isFinite(value) && value >= 0 ? value : null;
  };
  return { blob, duration: metric('x-speech-duration'), generationMs: metric('x-speech-generation-ms'), engine: response.headers.get('x-speech-engine') || null };
}

/** Gemeinsame lokale Einstellungen gelten auch beim markierten Vorlesen. */
export async function synthesizeSpeech(text, options = {}) {
  return (await synthesizeSpeechWithMetrics(text, options)).blob;
}
