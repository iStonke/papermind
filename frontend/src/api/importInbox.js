import { apiFetch, authHeaders, getBaseUrl } from './client.js';

export async function getImportInbox({ limit = 50 } = {}) {
  const search = new URLSearchParams();
  search.set('limit', String(Math.max(1, Math.min(Number(limit) || 50, 200))));
  return apiFetch(`/api/import/inbox?${search}`);
}

/**
 * Abonniert den Server-Sent-Events-Stream der Import-Inbox. Der Server pusht den
 * vollständigen Inbox-Status (gleiche Struktur wie getImportInbox) bei jeder
 * Änderung. Solange der Stream läuft, ist clientseitiges Polling nur Fallback.
 *
 * Bewusst fetch-basiert (statt EventSource): EventSource kann keinen
 * Authorization-Header setzen, der Stream ist aber wie alle API-Routen per
 * Bearer-Token geschützt. Wir lesen den Stream manuell und parsen die
 * SSE-Frames selbst.
 *
 * @param {(payload: object) => void} onPayload  Callback je Inbox-Event.
 * @param {{ onError?: (error: Error) => void, signal?: AbortSignal }} [options]
 * @returns {{ close: () => void }} Handle zum Beenden des Streams.
 */
export function subscribeImportInbox(onPayload, { onError = null, signal = null } = {}) {
  const controller = new AbortController();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  (async () => {
    let response;
    try {
      response = await fetch(`${getBaseUrl()}/api/import/inbox/events`, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { ...authHeaders(), Accept: 'text/event-stream' },
        signal: controller.signal
      });
    } catch (error) {
      if (!controller.signal.aborted && typeof onError === 'function') onError(error);
      return;
    }

    if (!response.ok || !response.body) {
      if (typeof onError === 'function') {
        const error = new Error(`Inbox-Stream nicht verfügbar (${response.status}).`);
        error.status = response.status;
        onError(error);
      }
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    try {
      // SSE-Frames sind durch eine Leerzeile getrennt; je Frame können mehrere
      // "data:"-Zeilen vorkommen, die zusammengehängt werden.
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let separatorIndex;
        while ((separatorIndex = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, separatorIndex);
          buffer = buffer.slice(separatorIndex + 2);
          const dataLines = frame
            .split('\n')
            .filter((line) => line.startsWith('data:'))
            .map((line) => line.slice(5).trimStart());
          if (dataLines.length === 0) continue; // Kommentar/Heartbeat
          try {
            onPayload(JSON.parse(dataLines.join('\n')));
          } catch {
            /* unvollständiges/ungültiges JSON ignorieren */
          }
        }
      }
      if (!controller.signal.aborted && typeof onError === 'function') {
        onError(new Error('Inbox-Stream beendet.'));
      }
    } catch (error) {
      if (!controller.signal.aborted && typeof onError === 'function') onError(error);
    }
  })();

  return {
    close() {
      controller.abort();
    }
  };
}

export async function claimImportInboxItems(itemIds = []) {
  return apiFetch('/api/import/inbox/claim', {
    method: 'POST',
    body: JSON.stringify({
      item_ids: Array.from(itemIds || []).map((id) => String(id || '').trim()).filter(Boolean)
    })
  });
}

export async function assignImportInboxItems(itemIds = []) {
  return apiFetch('/api/import/inbox/assign', {
    method: 'POST',
    body: JSON.stringify({
      item_ids: Array.from(itemIds || []).map((id) => String(id || '').trim()).filter(Boolean)
    })
  });
}

export async function discardImportInboxItems(itemIds = []) {
  return apiFetch('/api/import/inbox/discard', {
    method: 'POST',
    body: JSON.stringify({
      item_ids: Array.from(itemIds || []).map((id) => String(id || '').trim()).filter(Boolean)
    })
  });
}

export async function discardImportInboxSourcePages(sourceFileId, pageIndices = []) {
  const normalizedSourceFileId = String(sourceFileId || '').trim();
  return apiFetch(`/api/import/inbox/source/${encodeURIComponent(normalizedSourceFileId)}/pages/discard`, {
    method: 'POST',
    body: JSON.stringify({
      page_indices: Array.from(pageIndices || [])
        .map((index) => Number(index))
        .filter((index) => Number.isInteger(index) && index >= 0)
    })
  });
}
