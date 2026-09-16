/** Owns the inbox stream, fallback polling and their complete disposal. */
export function createImportInboxSync({ refresh, subscribe, onPayload, isOpen, onError = () => {} }) {
  let stream = null;
  let streamActive = false;
  let pollTimer = null;
  let reconnectTimer = null;
  let started = false;
  let disposed = false;
  let polling = false;

  function stopStream() {
    stream?.close();
    stream = null;
    streamActive = false;
  }

  function schedule(delay = null) {
    if (!started || disposed) return;
    window.clearTimeout(pollTimer);
    const nextDelay = delay ?? (document.hidden ? 60000 : streamActive ? 30000 : isOpen() ? 2000 : 5000);
    pollTimer = window.setTimeout(async () => {
      pollTimer = null;
      if (disposed) return;
      if (!polling) {
        polling = true;
        try {
          await refresh({ silent: true });
        } catch (error) {
          onError(error);
        } finally {
          polling = false;
        }
      }
      // An in-flight request must never resurrect a disposed workspace timer.
      schedule();
    }, nextDelay);
  }

  function startStream() {
    if (disposed || !started || stream || document.hidden || !window.ReadableStream) return;
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
    stream = subscribe((payload) => {
      if (disposed) return;
      streamActive = true;
      Promise.resolve(onPayload(payload, { allowAutoOpen: true })).catch(onError);
      schedule();
    }, {
      onError: () => {
        if (disposed) return;
        stopStream();
        schedule();
        if (!document.hidden && !reconnectTimer) {
          reconnectTimer = window.setTimeout(() => {
            reconnectTimer = null;
            startStream();
          }, 8000);
        }
      },
    });
  }

  function visibilityChanged() {
    schedule(document.hidden ? 60000 : 0);
    if (document.hidden) stopStream();
    else startStream();
  }

  function start() {
    if (disposed || started) return;
    started = true;
    document.addEventListener('visibilitychange', visibilityChanged);
    Promise.resolve(refresh({ silent: true, allowAutoOpen: false })).catch(onError);
    schedule();
    startStream();
  }

  function dispose() {
    disposed = true;
    window.clearTimeout(pollTimer);
    window.clearTimeout(reconnectTimer);
    stopStream();
    document.removeEventListener('visibilitychange', visibilityChanged);
  }

  return { start, schedule, dispose };
}
