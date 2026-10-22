export function abortableDelay(milliseconds, signal) {
  return new Promise(resolve => {
    const finish = () => { clearTimeout(timer); signal?.removeEventListener('abort', finish); resolve(); };
    const timer = setTimeout(finish, milliseconds);
    signal?.addEventListener('abort', finish, { once: true });
    if (signal?.aborted) finish();
  });
}
// One expensive analysis at a time. Cancellation also removes queued work and
// wakes backoff immediately; a removed document never blocks the next one.
export function createImportAnalysisQueue() {
  let tail = Promise.resolve(), closed = false;
  const jobs = new Map(), controls = new Map();
  return {
    jobs,
    enqueue(id, revision, run) {
      if (closed) return Promise.resolve();
      if (jobs.has(id)) return jobs.get(id);
      const controller = new AbortController();
      controls.set(id, { revision, controller });
      const job = tail.catch(() => {}).then(() => controller.signal.aborted ? undefined : run(controller.signal)).finally(() => {
        controller.abort();
        if (jobs.get(id) === job) jobs.delete(id);
        if (controls.get(id)?.controller === controller) controls.delete(id);
      });
      jobs.set(id, job); tail = job.catch(() => {}); return job;
    },
    reconcile(revisions) {
      for (const [id, item] of controls) if (revisions.get(id) !== item.revision) item.controller.abort();
    },
    clear() { for (const item of controls.values()) item.controller.abort(); jobs.clear(); controls.clear(); },
    close() { closed = true; this.clear(); },
  };
}
