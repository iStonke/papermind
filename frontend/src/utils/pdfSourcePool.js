// Leases prevent eviction from destroying a PDF while a page is rendering.
// Blob identity also invalidates same-id sources after scanner cleanup.
export function createPdfSourcePool(open, { maxSources = 3, maxBytes = 64 * 1024 * 1024 } = {}) {
  const entries = new Map();
  let closed = false;
  function destroy(entry) {
    if (entry.destroyed || entry.users) return;
    entry.destroyed = true;
    if (entries.get(entry.key) === entry) entries.delete(entry.key);
    void entry.promise.then(pdf => pdf.destroy()).catch(() => {});
  }
  function trim() {
    let bytes = [...entries.values()].reduce((total, entry) => total + entry.file.size, 0);
    for (const entry of [...entries.values()]) {
      if (entries.size <= maxSources && bytes <= maxBytes) break;
      if (!entry.users) { bytes -= entry.file.size; destroy(entry); }
    }
  }
  return {
    async acquire(key, file) {
      if (closed) throw new Error('PDF pool closed');
      let entry = entries.get(key);
      if (entry && entry.file !== file) { entry.stale = true; entries.delete(key); destroy(entry); entry = null; }
      if (!entry) {
        entry = { key, file, users: 0, stale: false, destroyed: false };
        entry.promise = Promise.resolve().then(() => file.arrayBuffer()).then(bytes => open(bytes));
        entries.set(key, entry);
      } else { entries.delete(key); entries.set(key, entry); }
      entry.users++;
      try {
        const pdf = await entry.promise;
        let released = false;
        return { pdf, release() {
          if (released) return; released = true; entry.users--;
          if (entry.stale || closed) destroy(entry); else trim();
        } };
      } catch (error) {
        entry.users--; entry.stale = true; destroy(entry); throw error;
      }
    },
    invalidate(key) { const entry = entries.get(key); if (entry) { entry.stale = true; entries.delete(key); destroy(entry); } },
    clear() { for (const entry of [...entries.values()]) { entry.stale = true; entries.delete(entry.key); destroy(entry); } },
    close() { closed = true; this.clear(); },
    get size() { return entries.size; },
  };
}
