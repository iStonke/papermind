// Local bounded numeric diagnostics. No document text, file names, source IDs,
// URLs or network reporting. Available through the component's diagnostics().
const EVENTS = new Set(['scan_start', 'first_scan_frame', 'source_received', 'first_sharp_preview', 'analysis_start', 'first_metadata', 'analysis_complete', 'commit_start', 'commit_complete', 'draft_saved', 'preview_render']);
const NUMBERS = new Set(['duration_ms', 'pages', 'bytes', 'cache_bytes', 'network_ms', 'ocr_ms', 'ai_ms', 'browser_ms']);
export function createImportDiagnostics({ now = () => performance.now(), limit = 200 } = {}) {
  const rows = [], starts = new Map(), onceKeys = new Set();
  function record(event, fields = {}) {
    if (!EVENTS.has(event)) return;
    const row = { event, at_ms: Math.round(now()) };
    for (const [key, value] of Object.entries(fields)) if (NUMBERS.has(key) && Number.isFinite(value) && value >= 0) row[key] = Math.round(value * 10) / 10;
    rows.push(row); if (rows.length > limit) rows.shift();
  }
  return {
    record,
    elapsed(key) { return starts.has(key) ? Math.max(0, now() - starts.get(key)) : undefined; },
    start(key, event) { starts.set(key, now()); record(event); if (starts.size > limit) starts.delete(starts.keys().next().value); },
    end(key, event, fields = {}) { const started = starts.get(key); record(event, { ...fields, ...(started == null ? {} : { duration_ms: now() - started }) }); starts.delete(key); },
    once(key, event, fields = {}) { if (onceKeys.has(key)) return; onceKeys.add(key); if (onceKeys.size > limit) onceKeys.delete(onceKeys.values().next().value); record(event, fields); },
    snapshot: () => rows.map(row => ({ ...row })),
    clear() { rows.length = 0; starts.clear(); onceKeys.clear(); },
  };
}
