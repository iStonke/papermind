import { onMounted, onBeforeUnmount } from 'vue';
import { logDevError } from '../stores/notifications';
import { useDocumentVisibility } from './useDocumentVisibility.js';

const STATUS_POLL_INTERVAL_MS = 5000;
const HIDDEN_POLL_INTERVAL_MS = 30000;

/**
 * Startet einen regelmäßigen Polling-Zyklus der Dokumentenliste,
 * solange Dokumente mit Status 'processing' vorhanden sind oder ein
 * aktiver OCR-Job läuft. Lifecycle-Hooks werden intern verwaltet.
 *
 * @param {Object} options
 * @param {import('vue').Ref}     options.documents           – Dokumentenliste aus dem Store
 * @param {import('vue').Ref}     options.hasActiveOcrJob     – Ob der ausgewählte Doc einen laufenden Job hat
 * @param {import('vue').Ref}     options.isLoadingDocuments  – Ladeindikator (kein Poll bei laufendem Fetch)
 * @param {import('vue').Ref}     options.selectedDocumentId  – Aktuell ausgewählte Doc-ID
 * @param {Function}              options.refreshDocumentStatuses – Lädt nur Statusfelder der aktiven Dokumente
 */
export function useOcrPolling({
  documents,
  hasActiveOcrJob,
  isLoadingDocuments,
  selectedDocumentId,
  refreshDocumentStatuses
}) {
  let statusPollTimer = null;
  let pollInFlight = false;
  const { onVisibilityChange } = useDocumentVisibility();
  let stopVisibility = null;

  async function pollOcrStatus() {
    if (isLoadingDocuments.value || pollInFlight) {
      return;
    }
    const processingIds = documents.value
      .filter((doc) => doc.status === 'processing' || ['queued', 'running'].includes(doc.ocr_status))
      .map((doc) => doc.id)
      .filter(Boolean);
    if (hasActiveOcrJob.value && selectedDocumentId.value) {
      processingIds.push(selectedDocumentId.value);
    }
    const uniqueIds = [...new Set(processingIds)].slice(0, 100);
    if (uniqueIds.length === 0) {
      return;
    }
    pollInFlight = true;
    try {
      await refreshDocumentStatuses(uniqueIds);
    } catch (error) {
      logDevError(error, 'ocr-polling');
    } finally {
      pollInFlight = false;
    }
  }

  function schedulePoll(delay = null) {
    if (statusPollTimer) window.clearTimeout(statusPollTimer);
    const nextDelay = delay ?? (
      document.hidden ? HIDDEN_POLL_INTERVAL_MS : STATUS_POLL_INTERVAL_MS
    );
    statusPollTimer = window.setTimeout(async () => {
      await pollOcrStatus();
      schedulePoll();
    }, nextDelay);
  }

  function handleVisibilityChange() {
    schedulePoll(document.hidden ? HIDDEN_POLL_INTERVAL_MS : 0);
  }

  onMounted(() => {
    stopVisibility = onVisibilityChange(handleVisibilityChange);
    schedulePoll();
  });

  onBeforeUnmount(() => {
    if (stopVisibility) {
      stopVisibility();
      stopVisibility = null;
    }
    if (statusPollTimer) {
      window.clearTimeout(statusPollTimer);
    }
  });
}
