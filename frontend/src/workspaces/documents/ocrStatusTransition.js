const ACTIVE_OCR_STATUSES = new Set(['queued', 'running']);
const TERMINAL_OCR_STATUSES = new Set(['done', 'failed']);

export function didOcrReachTerminalState(previousStatus, nextStatus) {
  return ACTIVE_OCR_STATUSES.has(String(previousStatus || ''))
    && TERMINAL_OCR_STATUSES.has(String(nextStatus || ''));
}
