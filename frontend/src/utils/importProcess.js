const ACTIVE = new Set(['queued', 'ocr', 'llm', 'lookup']);
export function setImportAnalysisState(meta, phase, { reconnecting = false } = {}) {
  if (!['idle', 'queued', 'ocr', 'llm', 'lookup', 'complete', 'interrupted', 'error'].includes(phase)) throw new Error('Unknown analysis phase');
  meta.analysisState = phase;
  meta.analysisPhase = phase;
  meta.analysisPending = ACTIVE.has(phase) && phase !== 'lookup';
  meta.analysisLookupPending = phase === 'lookup';
  meta.analysisReconnecting = meta.analysisPending && reconnecting;
  meta.titleSuggestionStatus = phase === 'idle' ? 'idle' : phase === 'ocr' ? 'pending_ocr'
    : ACTIVE.has(phase) ? 'working' : phase === 'complete' ? 'ready' : phase;
}
// A single precedence table controls the visible process. Background analysis
// may overlap uploads, but can never replace their status or unlock a commit.
export function importProcessState({ committing, scanning, cleanup, refreshing, uploading, analysis, lookup, pages = 0, conflict }) {
  const phase = conflict ? 'conflict' : committing ? 'committing' : scanning ? 'scanning' : cleanup ? 'cleanup'
    : refreshing ? 'refreshing' : uploading ? 'uploading' : ACTIVE.has(analysis) ? analysis : lookup ? 'lookup' : 'idle';
  return { phase, busy: !['idle', 'conflict'].includes(phase), blocksCommit: !pages || ['conflict', 'committing', 'scanning', 'cleanup', 'refreshing', 'uploading'].includes(phase) };
}
