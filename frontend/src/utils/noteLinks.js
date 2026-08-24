const EMAIL_ADDRESS = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const EXPLICIT_SCHEME = /^[a-z][a-z0-9+.-]*:/i;
const ALLOWED_PROTOCOLS = new Set(['http:', 'https:', 'mailto:']);

/**
 * Normalisiert einen vom Benutzer eingegebenen externen Link. PaperMind
 * erlaubt bewusst nur Web- und Mail-Links; interne Ziele bleiben [[Verweise]].
 */
export function normalizeNoteHref(value) {
  const raw = String(value || '').trim();
  if (!raw || /[\u0000-\u001f\u007f\s]/.test(raw)) return '';

  let candidate = raw;
  if (EMAIL_ADDRESS.test(candidate)) candidate = `mailto:${candidate}`;
  else if (!EXPLICIT_SCHEME.test(candidate)) candidate = `https://${candidate}`;

  try {
    const parsed = new URL(candidate);
    if (!ALLOWED_PROTOCOLS.has(parsed.protocol)) return '';
    if ((parsed.protocol === 'http:' || parsed.protocol === 'https:') && !parsed.hostname) return '';
    if (parsed.protocol === 'mailto:' && !EMAIL_ADDRESS.test(parsed.pathname)) return '';
    return parsed.href;
  } catch {
    return '';
  }
}

export function noteHrefLabel(value, normalizedHref = normalizeNoteHref(value)) {
  const raw = String(value || '').trim();
  if (raw) return raw;
  return String(normalizedHref || '').replace(/^mailto:/i, '');
}
