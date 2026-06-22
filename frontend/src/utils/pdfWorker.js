import pdfWorkerSrc from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

// Der Worker-Inhalt kann bei reinen nginx-/Header-Korrekturen denselben
// Vite-Dateihash behalten. Eine explizite Versionskennung verhindert, dass
// Safari eine zuvor mit falschem MIME-Typ gecachte Antwort wiederverwendet.
export const PDF_WORKER_SRC = `${pdfWorkerSrc}?pm-worker=2`;
