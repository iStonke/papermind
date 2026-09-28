import { authHeaders, getBaseUrl } from './client.js';

const DEFAULT_ERROR = 'Der markierte Text konnte nicht vorgelesen werden.';

async function speechError(response) {
  try {
    const payload = await response.json();
    return new Error(payload?.error?.message || DEFAULT_ERROR);
  } catch {
    return new Error(DEFAULT_ERROR);
  }
}

/** Erzeugt die WAV-Datei lokal im PaperMind-Backend (Piper, keine Cloud). */
export async function synthesizeSpeech(text, { signal, voice = 'standard', languageMode = 'auto' } = {}) {
  const response = await fetch(`${getBaseUrl()}/api/tts/speech`, {
    method: 'POST',
    credentials: 'include',
    cache: 'no-store',
    headers: {
      ...authHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text, voice, language_mode: languageMode }),
    signal,
  });
  if (!response.ok) throw await speechError(response);
  const contentType = String(response.headers.get('content-type') || '').toLowerCase();
  if (!contentType.includes('audio/wav')) throw new Error(DEFAULT_ERROR);
  return response.blob();
}
