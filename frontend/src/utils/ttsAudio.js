const DEFAULT_CHUNK_CHARS = 6000;

function ascii(view, offset, length) {
  return String.fromCharCode(...new Uint8Array(view.buffer, view.byteOffset + offset, length));
}

function writeAscii(view, offset, value) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function parseWav(buffer) {
  const view = new DataView(buffer);
  if (view.byteLength < 12 || ascii(view, 0, 4) !== 'RIFF' || ascii(view, 8, 4) !== 'WAVE') {
    throw new Error('Die erzeugte Audiodatei ist ungültig.');
  }

  let format = null;
  const dataParts = [];
  for (let offset = 12; offset + 8 <= view.byteLength;) {
    const id = ascii(view, offset, 4);
    const size = view.getUint32(offset + 4, true);
    const start = offset + 8;
    const end = start + size;
    if (end > view.byteLength) throw new Error('Die erzeugte Audiodatei ist unvollständig.');
    const bytes = new Uint8Array(buffer.slice(start, end));
    if (id === 'fmt ') format = bytes;
    if (id === 'data') dataParts.push(bytes);
    offset = end + (size % 2);
  }
  if (!format || !dataParts.length) throw new Error('Die erzeugte Audiodatei enthält keine Audiospur.');
  return { format, dataParts };
}

function equalBytes(left, right) {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

export function splitSpeechText(text, maxChars = DEFAULT_CHUNK_CHARS) {
  const remainingParts = [String(text || '').replace(/\s+/g, ' ').trim()];
  const chunks = [];
  while (remainingParts.length) {
    const remaining = remainingParts.shift();
    if (!remaining) continue;
    if (remaining.length <= maxChars) {
      chunks.push(remaining);
      continue;
    }
    const window = remaining.slice(0, maxChars + 1);
    const minimum = Math.floor(maxChars * 0.55);
    let cut = -1;
    for (const match of window.matchAll(/[.!?;:]\s+/g)) {
      if (match.index >= minimum && match.index + match[0].length <= maxChars) {
        cut = match.index + match[0].length;
      }
    }
    if (cut < 0) cut = window.lastIndexOf(' ', maxChars);
    if (cut <= 0) cut = maxChars;
    chunks.push(remaining.slice(0, cut).trim());
    remainingParts.unshift(remaining.slice(cut).trim());
  }
  return chunks;
}

export async function mergeWavBlobs(blobs) {
  if (!blobs.length) throw new Error('Es wurde keine Audiodatei erzeugt.');
  if (blobs.length === 1) return blobs[0];

  const wavs = await Promise.all(blobs.map(async (blob) => parseWav(await blob.arrayBuffer())));
  const format = wavs[0].format;
  if (!wavs.every((wav) => equalBytes(wav.format, format))) {
    throw new Error('Die erzeugten Audioteile haben unterschiedliche Formate.');
  }
  const parts = wavs.flatMap((wav) => wav.dataParts);
  const dataSize = parts.reduce((sum, part) => sum + part.byteLength, 0);
  const formatPadding = format.byteLength % 2;
  const dataPadding = dataSize % 2;
  const buffer = new ArrayBuffer(12 + 8 + format.byteLength + formatPadding + 8 + dataSize + dataPadding);
  const view = new DataView(buffer);
  writeAscii(view, 0, 'RIFF');
  view.setUint32(4, buffer.byteLength - 8, true);
  writeAscii(view, 8, 'WAVE');
  writeAscii(view, 12, 'fmt ');
  view.setUint32(16, format.byteLength, true);
  new Uint8Array(buffer, 20, format.byteLength).set(format);
  const dataHeader = 20 + format.byteLength + formatPadding;
  writeAscii(view, dataHeader, 'data');
  view.setUint32(dataHeader + 4, dataSize, true);
  let dataOffset = dataHeader + 8;
  for (const part of parts) {
    new Uint8Array(buffer, dataOffset, part.byteLength).set(part);
    dataOffset += part.byteLength;
  }
  return new Blob([buffer], { type: 'audio/wav' });
}
