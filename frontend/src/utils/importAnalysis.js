export function analysisPending(payload) {
  if (typeof payload?.meta?.analysis_pending === 'boolean') return payload.meta.analysis_pending;
  return payload?.status === 'pending_ocr' || Boolean(payload?.meta?.refinement_pending);
}

export function acceptAnalysisSnapshot(meta, payload, revision) {
  const incoming = payload.meta || {};
  const previous = meta.analysisSnapshot;
  const rank = incoming.analysis_phase === 'llm' ? 2 : incoming.analysis_phase === 'rule' ? 1 : 0;
  const timestamp = Date.parse(incoming.cached_at || '') || 0;
  const startedAt = Number(incoming.analysis_started_at || 0);
  const newGeneration = previous?.revision === revision && startedAt > (previous.startedAt || 0)
    && incoming.analysis_job_id !== previous.jobId;
  if (previous?.revision === revision) {
    if (startedAt && previous.startedAt > startedAt) return false;
    if (incoming.analysis_job_id && incoming.analysis_job_id === previous.jobId
      && Number(incoming.analysis_sequence || 0) < previous.sequence) return false;
    if (timestamp && previous.timestamp > timestamp) return false;
    if (payload.status === 'ready' && rank && rank < previous.rank && !newGeneration) return false;
    if (previous.complete && analysisPending(payload) && startedAt <= previous.startedAt
      && Number(incoming.analysis_sequence || 0) <= previous.sequence) return false;
    if (['error', 'failed', 'pending_ocr'].includes(payload.status) && previous.complete
      && incoming.analysis_job_id !== previous.jobId) return false;
  }
  if (payload.status === 'ready') meta.analysisSnapshot = {
    revision, rank: Math.max(rank, previous?.revision === revision && !newGeneration ? previous.rank : 0), timestamp,
    startedAt: startedAt || (previous?.revision === revision ? previous.startedAt : 0),
    jobId: incoming.analysis_job_id || (previous?.revision === revision ? previous.jobId : null),
    sequence: Number(incoming.analysis_sequence || 0) || (previous?.revision === revision ? previous.sequence : 0),
    complete: !analysisPending(payload),
  };
  return true;
}

export function transientAnalysisError(error) {
  return error?.name === 'AbortError' || error?.code === 'REQUEST_TIMEOUT' || error instanceof TypeError
    || [408, 409, 425, 429, 500, 502, 503, 504].includes(Number(error?.status));
}
