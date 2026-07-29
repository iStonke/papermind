export const THUMBNAIL_RETRY_BASE_DELAYS_MS = Object.freeze([500, 1_600, 5_000]);

function stableJitter(value) {
  let hash = 0;
  for (const character of String(value || '')) {
    hash = ((hash * 31) + character.charCodeAt(0)) >>> 0;
  }
  return hash % 300;
}

/**
 * Liefert die Wartezeit für einen Thumbnail-Wiederholungsversuch.
 * Ein stabiler, dokumentabhängiger Versatz verhindert, dass nach einem kurzen
 * Ausfall alle sichtbaren Bilder gleichzeitig erneut angefordert werden.
 */
export function thumbnailRetryDelay(attempt, documentId) {
  const normalizedAttempt = Number(attempt);
  if (
    !Number.isInteger(normalizedAttempt)
    || normalizedAttempt < 0
    || normalizedAttempt >= THUMBNAIL_RETRY_BASE_DELAYS_MS.length
  ) {
    return null;
  }
  return THUMBNAIL_RETRY_BASE_DELAYS_MS[normalizedAttempt] + stableJitter(documentId);
}
