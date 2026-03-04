export function isIOS(): boolean {
  if (typeof navigator === 'undefined' || typeof document === 'undefined') {
    return false;
  }
  const ua = String(navigator.userAgent || '');
  const iOS = /iPad|iPhone|iPod/.test(ua);
  const iPadOS13 = /Macintosh/.test(ua) && 'ontouchend' in document;
  return iOS || iPadOS13;
}
