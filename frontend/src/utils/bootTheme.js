const KEY = 'pm-boot-theme-mode';
export function readBootTheme() {
  let mode;
  try { mode = window.localStorage.getItem(KEY); } catch { /* Storage optional. */ }
  if (mode === 'light' || mode === 'dark') return mode;
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
export function rememberBootTheme(mode) {
  try { window.localStorage.setItem(KEY, ['light', 'dark'].includes(mode) ? mode : 'system'); } catch { /* Storage optional. */ }
}
