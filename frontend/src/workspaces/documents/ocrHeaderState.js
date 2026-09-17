export function resolveOcrHeaderPresentation({
  hasDocument,
  ocrStatus,
  inProgress,
  hasCompletedOcr,
  qualityStatus
}) {
  if (!hasDocument) {
    return { status: null, showMenuAction: false };
  }

  if (String(ocrStatus || '').toLowerCase() === 'failed') {
    return {
      status: {
        tone: 'failed',
        text: 'OCR fehlgeschlagen',
        icon: 'mdi-refresh'
      },
      showMenuAction: false
    };
  }

  if (inProgress) {
    return {
      status: { tone: 'progress', text: 'OCR läuft…', icon: '' },
      showMenuAction: false
    };
  }

  if (hasCompletedOcr) {
    const normalizedQualityStatus = String(qualityStatus || '').toLowerCase();
    if (normalizedQualityStatus === 'error') {
      return {
        status: { tone: 'error', text: 'OCR prüfen', icon: 'mdi-alert-circle-outline' },
        showMenuAction: false
      };
    }
    if (normalizedQualityStatus === 'warning') {
      return {
        status: { tone: 'warning', text: 'OCR unsicher', icon: 'mdi-alert-circle-outline' },
        showMenuAction: false
      };
    }
    return {
      status: { tone: 'done', text: 'OCR', icon: 'mdi-check-circle-outline' },
      showMenuAction: false
    };
  }

  return { status: null, showMenuAction: true };
}
