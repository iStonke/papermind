function normalizeApiBaseUrl(value) {
  const raw = String(value || '').trim().replace(/\/$/, '');
  if (!raw || raw.includes('<') || raw.includes('>')) {
    return '';
  }

  try {
    const parsed = new URL(raw);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.toString().replace(/\/$/, '');
    }
  } catch {
    return '';
  }

  return '';
}

export const API_BASE_URL = normalizeApiBaseUrl(import.meta.env?.VITE_API_BASE_URL);
