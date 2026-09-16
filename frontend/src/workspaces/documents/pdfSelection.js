function isPdfCandidate(file) {
  const filename = String(file?.name || '').toLowerCase();
  if (filename.endsWith('.pdf')) {
    return true;
  }
  return String(file?.type || '').toLowerCase() === 'application/pdf';
}

function normalizeRelativePath(pathValue) {
  return String(pathValue || '')
    .replace(/\\/g, '/')
    .replace(/^\/+/, '')
    .trim();
}

function buildSelectionDedupKey(file, relativePath = '') {
  const filename = String(file?.name || '').trim();
  const size = Number(file?.size || 0);
  const lastModified = Number(file?.lastModified || 0);
  return `${filename}|${size}|${lastModified}|${relativePath}`;
}

export function selectPdfFiles(files, source) {
  const dedupe = new Set();
  const acceptedFiles = [];
  let skippedNonPdf = 0;
  let skippedDuplicates = 0;

  for (const file of files) {
    const relativePath = source === 'folder' ? normalizeRelativePath(file?.webkitRelativePath) : '';
    const dedupeKey = buildSelectionDedupKey(file, relativePath);
    if (dedupe.has(dedupeKey)) {
      skippedDuplicates += 1;
      continue;
    }
    dedupe.add(dedupeKey);

    if (!isPdfCandidate(file)) {
      skippedNonPdf += 1;
      continue;
    }

    acceptedFiles.push(file);
  }

  return {
    files: acceptedFiles,
    skippedNonPdf,
    skippedDuplicates
  };
}
