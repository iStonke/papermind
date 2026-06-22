// Recovery module for browsers that still execute an old, cached application
// bundle after a deployment. Missing hashed JS chunks are redirected here by
// nginx. A cache-busted navigation then loads the current index.html.
(() => {
  const recoveryKey = 'pm.staleAssetRecoveryAt';
  const now = Date.now();
  const previous = Number(window.sessionStorage.getItem(recoveryKey) || 0);

  // Avoid a reload loop if the server itself is incomplete.
  if (previous && now - previous < 30_000) {
    console.error('PaperMind asset recovery failed: server assets are incomplete.');
    return;
  }

  window.sessionStorage.setItem(recoveryKey, String(now));
  const target = new URL(window.location.href);
  target.searchParams.set('pm-recover', String(now));
  window.location.replace(target.toString());
})();
