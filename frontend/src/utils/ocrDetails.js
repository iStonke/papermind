import { formatDateTime } from './dates.js';

const labels = { good: 'Gut', warning: 'Eingeschränkt', error: 'Schlecht' };
const sources = { ocr: 'Durch OCR erkannt', embedded: 'Bereits im PDF enthalten', none: 'Noch kein Text vorhanden' };
const number = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 });
const isQuality = value => ['good', 'warning', 'error'].includes(value);

function validScore(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100 ? value : null;
}

export function resolveOcrQuality(document = {}) {
  const currentScore = validScore(document.ocr_confidence_score);
  const currentQuality = isQuality(document.ocr_quality_status) ? document.ocr_quality_status : null;
  const stored = document.flags?.ocr?.quality || {};
  // Prefer a complete current assessment to mixing it with an older result.
  const useStored = currentScore === null && currentQuality === null;
  const average = stored.avg_confidence;
  const storedScore = validScore(stored.confidence_score)
    ?? (typeof average === 'number' && Number.isFinite(average) && average >= 0 && average <= 1
      ? Math.round(average * 1000) / 10 : null);
  const score = useStored ? storedScore : currentScore;
  const quality = (useStored ? (isQuality(stored.status) ? stored.status : null) : currentQuality)
    || (score === null ? null : score >= 80 ? 'good' : score >= 60 ? 'warning' : 'error');
  const message = useStored ? stored.message || document.ocr_quality_message : document.ocr_quality_message;
  return { score, quality, message: typeof message === 'string' ? message : '' };
}

export function resolveOcrDetails(document = {}, tone = 'done') {
  const jobs = (document.jobs || []).filter(job => job.type === 'OCR');
  const latest = [...jobs].sort((a, b) => (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0))[0];
  const inProgress = tone === 'progress';
  const failed = tone === 'failed';
  const assessment = resolveOcrQuality(document);
  const score = !inProgress && !failed ? assessment.score : null;
  const quality = !inProgress && !failed ? assessment.quality : null;
  const needsAssessment = !inProgress && !failed && quality === null;
  let seconds = !inProgress && !failed ? document.ocr_processing_seconds : null;
  if (!(typeof seconds === 'number' && Number.isFinite(seconds) && seconds >= 0)) {
    const start = Date.parse(latest?.started_at), end = Date.parse(latest?.finished_at);
    seconds = !inProgress && Number.isFinite(start) && Number.isFinite(end) && end >= start ? (end - start) / 1000 : null;
  }
  const finished = !inProgress ? formatDateTime(latest?.finished_at) : '-';
  const text = typeof document.text_content === 'string' ? document.text_content : '';
  const roundedSeconds = seconds === null ? 0 : Math.round(seconds);
  return {
    quality,
    needsAssessment,
    qualityLabel: labels[quality] || (inProgress ? 'Wird ermittelt' : failed ? 'Nicht bewertet' : 'Noch nicht bewertet'),
    score,
    scoreLabel: score === null ? '' : `${number.format(score)} %`,
    message: inProgress ? 'Die Qualität wird nach Abschluss der Texterkennung bewertet.'
      : failed ? 'Die Texterkennung konnte nicht abgeschlossen werden. Du kannst sie erneut starten.'
        : needsAssessment ? 'Führe die Texterkennung erneut aus, um eine Qualitätsbewertung zu erhalten.' : assessment.message || '',
    status: failed ? 'Fehlgeschlagen' : inProgress ? (latest?.status === 'queued' ? 'In Warteschlange' : 'Wird verarbeitet') : 'Abgeschlossen',
    duration: seconds === null ? '' : seconds < 1 ? 'Unter 1 Sekunde' : seconds < 60 ? `${number.format(seconds)} ${seconds === 1 ? 'Sekunde' : 'Sekunden'}`
      : `${Math.floor(roundedSeconds / 60)} Min. ${roundedSeconds % 60} Sek.`,
    finished: finished === '-' ? '' : finished,
    source: sources[document.text_source] || '',
    text,
    hasText: Boolean(text.trim())
  };
}
