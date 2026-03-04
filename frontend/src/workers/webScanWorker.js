const MIN_SAMPLE_COUNT = 20;

const config = {
  detectionEngine: 'heuristic',
  opencvUrl: '',
  processingEnabled: true
};

const runtimeState = {
  cvReady: false,
  cvInitAttempted: false,
  cvInitPromise: null
};

self.onmessage = (event) => {
  const message = event?.data || {};
  const type = String(message.type || '');

  if (type === 'configure') {
    void handleConfigure(message);
    return;
  }

  if (type === 'analyze') {
    void handleAnalyze(message);
    return;
  }

  if (type === 'processPage') {
    void handleProcessPage(message);
  }
};

async function handleConfigure(message) {
  const requestedEngine = String(message.detectionEngine || '').trim().toLowerCase();
  const normalizedEngine = requestedEngine === 'opencv' ? 'opencv' : 'heuristic';

  config.detectionEngine = normalizedEngine;
  config.opencvUrl = String(message.opencvUrl || '').trim();
  config.processingEnabled = Boolean(message.processingEnabled !== false);

  if (normalizedEngine === 'opencv') {
    await ensureOpenCvReady();
  }

  self.postMessage({
    type: 'configured',
    detectionEngineRequested: normalizedEngine,
    detectionEngineActive: runtimeState.cvReady ? 'opencv' : 'heuristic',
    processingSupported: canProcessInWorker()
  });
}

async function handleAnalyze(message) {
  const width = Math.max(1, Number(message.width) || 0);
  const height = Math.max(1, Number(message.height) || 0);
  const buffer = message.buffer;
  const requestId = Number(message.requestId) || 0;

  if (!(buffer instanceof ArrayBuffer) || width <= 2 || height <= 2) {
    self.postMessage({
      type: 'result',
      requestId,
      ...makeEmptyDetectionResult(),
      engineUsed: 'none'
    });
    return;
  }

  try {
    const rgba = new Uint8ClampedArray(buffer);
    let detection = null;
    let engineUsed = 'heuristic';

    if (config.detectionEngine === 'opencv') {
      const cvReady = await ensureOpenCvReady();
      if (cvReady) {
        try {
          const cvResult = analyzeFrameWithOpenCv(rgba, width, height);
          if (cvResult?.quad) {
            detection = cvResult;
            engineUsed = 'opencv';
          }
        } catch {
          // ignore and fall back
        }
      }
    }

    if (!detection) {
      detection = analyzeFrameWithHeuristics(rgba, width, height);
      engineUsed = 'heuristic';
    }

    self.postMessage({
      type: 'result',
      requestId,
      ...normalizeDetectionResult(detection),
      engineUsed
    });
  } catch {
    self.postMessage({
      type: 'result',
      requestId,
      ...makeEmptyDetectionResult(),
      engineUsed: 'error'
    });
  }
}

async function handleProcessPage(message) {
  const requestId = Number(message.requestId) || 0;
  const imageBuffer = message.imageBuffer;

  if (!(imageBuffer instanceof ArrayBuffer)) {
    self.postMessage({
      type: 'processResult',
      requestId,
      ok: false,
      supported: canProcessInWorker(),
      error: 'imageBuffer missing'
    });
    return;
  }

  if (!config.processingEnabled || !canProcessInWorker()) {
    self.postMessage({
      type: 'processResult',
      requestId,
      ok: false,
      supported: false,
      error: 'worker processing unsupported'
    });
    return;
  }

  try {
    const result = await processPageInWorker({
      imageBuffer,
      mimeType: message.mimeType,
      quadNorm: message.quad,
      filterMode: message.filterMode,
      rotationTurns: message.rotationTurns,
      maxLongEdge: message.maxLongEdge
    });

    self.postMessage(
      {
        type: 'processResult',
        requestId,
        ok: true,
        supported: true,
        buffer: result.buffer,
        width: result.width,
        height: result.height
      },
      [result.buffer]
    );
  } catch {
    self.postMessage({
      type: 'processResult',
      requestId,
      ok: false,
      supported: true,
      error: 'processing failed'
    });
  }
}

function canProcessInWorker() {
  const hasConvertToBlob =
    typeof OffscreenCanvas !== 'undefined' &&
    typeof OffscreenCanvas.prototype?.convertToBlob === 'function';
  return (
    typeof OffscreenCanvas !== 'undefined' &&
    typeof createImageBitmap === 'function' &&
    typeof Blob !== 'undefined' &&
    hasConvertToBlob
  );
}

async function ensureOpenCvReady() {
  if (runtimeState.cvReady) {
    return true;
  }

  if (typeof self.cv !== 'undefined' && typeof self.cv.Mat === 'function') {
    runtimeState.cvReady = true;
    return true;
  }

  if (runtimeState.cvInitPromise) {
    return runtimeState.cvInitPromise;
  }

  if (runtimeState.cvInitAttempted) {
    return false;
  }
  runtimeState.cvInitAttempted = true;

  const opencvUrl = String(config.opencvUrl || '').trim();
  if (!opencvUrl || typeof importScripts !== 'function') {
    return false;
  }

  runtimeState.cvInitPromise = new Promise((resolve) => {
    let resolved = false;
    const finish = (value) => {
      if (resolved) {
        return;
      }
      resolved = true;
      runtimeState.cvReady = Boolean(value);
      resolve(Boolean(value));
    };

    const timeout = setTimeout(() => {
      finish(runtimeState.cvReady);
    }, 7000);

    try {
      const previousModule = self.Module || {};
      const previousRuntimeInit = previousModule.onRuntimeInitialized;
      self.Module = {
        ...previousModule,
        onRuntimeInitialized: () => {
          try {
            previousRuntimeInit?.();
          } catch {
            // ignore
          }
          clearTimeout(timeout);
          finish(true);
        }
      };

      importScripts(opencvUrl);

      if (typeof self.cv !== 'undefined' && typeof self.cv.Mat === 'function') {
        if (typeof self.cv.onRuntimeInitialized === 'function') {
          const previousCvRuntimeInit = self.cv.onRuntimeInitialized;
          self.cv.onRuntimeInitialized = () => {
            try {
              previousCvRuntimeInit?.();
            } catch {
              // ignore
            }
            clearTimeout(timeout);
            finish(true);
          };
        } else {
          clearTimeout(timeout);
          finish(true);
        }
      }
    } catch {
      clearTimeout(timeout);
      finish(false);
    }
  });

  return runtimeState.cvInitPromise;
}

function analyzeFrameWithOpenCv(pixels, width, height) {
  const cv = self.cv;
  if (!cv || typeof cv.Mat !== 'function') {
    return makeEmptyDetectionResult();
  }

  const imageData = new ImageData(new Uint8ClampedArray(pixels), width, height);
  const src = cv.matFromImageData(imageData);
  const gray = new cv.Mat();
  const blur = new cv.Mat();
  const edges = new cv.Mat();
  const contours = new cv.MatVector();
  const hierarchy = new cv.Mat();

  let bestQuad = null;
  let bestArea = 0;

  try {
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY, 0);
    cv.GaussianBlur(gray, blur, new cv.Size(5, 5), 0, 0, cv.BORDER_DEFAULT);
    cv.Canny(blur, edges, 75, 200);
    cv.findContours(edges, contours, hierarchy, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE);

    const frameArea = width * height;
    for (let i = 0; i < contours.size(); i += 1) {
      const contour = contours.get(i);
      const area = Math.abs(cv.contourArea(contour));
      if (area < frameArea * 0.12 || area <= bestArea) {
        contour.delete();
        continue;
      }

      const perimeter = cv.arcLength(contour, true);
      const approx = new cv.Mat();
      cv.approxPolyDP(contour, approx, 0.02 * perimeter, true);

      if (approx.rows === 4) {
        const points = extractQuadPoints(approx);
        const ordered = orderQuadPoints(points);
        if (ordered) {
          bestQuad = ordered;
          bestArea = area;
        }
      }

      approx.delete();
      contour.delete();
    }

    if (!bestQuad) {
      return makeEmptyDetectionResult();
    }

    const areaRatio = bestArea / Math.max(1, width * height);
    const bbox = boundingBox(bestQuad);
    const bboxArea = Math.max(1, (bbox.maxX - bbox.minX) * (bbox.maxY - bbox.minY));
    const rectangularity = clamp(bestArea / bboxArea, 0, 1);
    const anglesScore = computeAngleScore(bestQuad);
    const edgeStrength = computeEdgeStrengthFromMap(edges, width, height, bestQuad);
    const areaScore = clamp((areaRatio - 0.15) / 0.35, 0, 1);

    const confidence = clamp(
      0.35 * areaScore +
        0.25 * rectangularity +
        0.25 * anglesScore +
        0.15 * edgeStrength,
      0,
      1
    );

    return normalizeDetectionResult({
      quad: bestQuad.map((point) => ({
        x: clamp(point.x / width, 0, 1),
        y: clamp(point.y / height, 0, 1)
      })),
      confidence,
      metrics: {
        areaRatio,
        jitter: 0,
        edgeStrength,
        anglesScore,
        bbox: {
          x: clamp(bbox.minX / width, 0, 1),
          y: clamp(bbox.minY / height, 0, 1),
          width: clamp((bbox.maxX - bbox.minX) / width, 0, 1),
          height: clamp((bbox.maxY - bbox.minY) / height, 0, 1)
        }
      }
    });
  } catch {
    return makeEmptyDetectionResult();
  } finally {
    src.delete();
    gray.delete();
    blur.delete();
    edges.delete();
    contours.delete();
    hierarchy.delete();
  }
}

function analyzeFrameWithHeuristics(pixels, width, height) {
  const gray = new Float32Array(width * height);
  for (let i = 0, p = 0; i < gray.length; i += 1, p += 4) {
    gray[i] = pixels[p] * 0.299 + pixels[p + 1] * 0.587 + pixels[p + 2] * 0.114;
  }

  const gradient = new Float32Array(width * height);
  let sum = 0;
  let sumSquares = 0;
  let count = 0;

  for (let y = 1; y < height - 1; y += 1) {
    const rowOffset = y * width;
    for (let x = 1; x < width - 1; x += 1) {
      const index = rowOffset + x;
      const gx = gray[index + 1] - gray[index - 1];
      const gy = gray[index + width] - gray[index - width];
      const magnitude = Math.abs(gx) + Math.abs(gy);
      gradient[index] = magnitude;
      sum += magnitude;
      sumSquares += magnitude * magnitude;
      count += 1;
    }
  }

  if (count <= 0) {
    return makeEmptyDetectionResult();
  }

  const mean = sum / count;
  const variance = Math.max(0, sumSquares / count - mean * mean);
  const threshold = mean + Math.sqrt(variance) * 1.15;

  const leftSamples = [];
  const rightSamples = [];
  const rowStart = Math.floor(height * 0.06);
  const rowEnd = Math.ceil(height * 0.94);
  for (let y = rowStart; y < rowEnd; y += 1) {
    const rowOffset = y * width;
    let left = -1;
    let right = -1;

    for (let x = 1; x < width - 1; x += 1) {
      if (gradient[rowOffset + x] > threshold) {
        left = x;
        break;
      }
    }

    for (let x = width - 2; x >= 1; x -= 1) {
      if (gradient[rowOffset + x] > threshold) {
        right = x;
        break;
      }
    }

    if (left >= 0 && right >= 0 && right - left > width * 0.24) {
      leftSamples.push({ x: left, y });
      rightSamples.push({ x: right, y });
    }
  }

  const topSamples = [];
  const bottomSamples = [];
  const colStart = Math.floor(width * 0.06);
  const colEnd = Math.ceil(width * 0.94);
  for (let x = colStart; x < colEnd; x += 1) {
    let top = -1;
    let bottom = -1;

    for (let y = 1; y < height - 1; y += 1) {
      if (gradient[y * width + x] > threshold) {
        top = y;
        break;
      }
    }

    for (let y = height - 2; y >= 1; y -= 1) {
      if (gradient[y * width + x] > threshold) {
        bottom = y;
        break;
      }
    }

    if (top >= 0 && bottom >= 0 && bottom - top > height * 0.24) {
      topSamples.push({ x, y: top });
      bottomSamples.push({ x, y: bottom });
    }
  }

  if (
    leftSamples.length < MIN_SAMPLE_COUNT ||
    rightSamples.length < MIN_SAMPLE_COUNT ||
    topSamples.length < MIN_SAMPLE_COUNT ||
    bottomSamples.length < MIN_SAMPLE_COUNT
  ) {
    return makeEmptyDetectionResult();
  }

  const topLine = fitLineYFromX(topSamples);
  const bottomLine = fitLineYFromX(bottomSamples);
  const leftLine = fitLineXFromY(leftSamples);
  const rightLine = fitLineXFromY(rightSamples);
  if (!topLine || !bottomLine || !leftLine || !rightLine) {
    return makeEmptyDetectionResult();
  }

  const topLeft = intersectLines(topLine, leftLine);
  const topRight = intersectLines(topLine, rightLine);
  const bottomRight = intersectLines(bottomLine, rightLine);
  const bottomLeft = intersectLines(bottomLine, leftLine);

  const ordered = [topLeft, topRight, bottomRight, bottomLeft].map((point) => ({
    x: clamp(point?.x || 0, 0, width - 1),
    y: clamp(point?.y || 0, 0, height - 1)
  }));

  const area = polygonArea(ordered);
  const frameArea = width * height;
  const areaRatio = area / Math.max(1, frameArea);

  if (!Number.isFinite(areaRatio) || areaRatio < 0.12 || areaRatio > 0.99) {
    return makeEmptyDetectionResult();
  }

  const bbox = boundingBox(ordered);
  const bboxArea = Math.max(1, (bbox.maxX - bbox.minX) * (bbox.maxY - bbox.minY));
  const rectangularity = clamp(area / bboxArea, 0, 1);
  const anglesScore = computeAngleScore(ordered);
  const edgeStrength = computeEdgeStrengthFromGradient(gradient, width, height, ordered, threshold);
  const areaScore = clamp((areaRatio - 0.15) / 0.35, 0, 1);

  const confidence = clamp(
    0.35 * areaScore +
      0.25 * rectangularity +
      0.25 * anglesScore +
      0.15 * edgeStrength,
    0,
    1
  );

  return normalizeDetectionResult({
    quad: ordered.map((point) => ({
      x: clamp(point.x / width, 0, 1),
      y: clamp(point.y / height, 0, 1)
    })),
    confidence,
    metrics: {
      areaRatio,
      jitter: 0,
      edgeStrength,
      anglesScore,
      bbox: {
        x: clamp(bbox.minX / width, 0, 1),
        y: clamp(bbox.minY / height, 0, 1),
        width: clamp((bbox.maxX - bbox.minX) / width, 0, 1),
        height: clamp((bbox.maxY - bbox.minY) / height, 0, 1)
      }
    }
  });
}

async function processPageInWorker({ imageBuffer, mimeType, quadNorm, filterMode, rotationTurns, maxLongEdge }) {
  const sourceBlob = new Blob([imageBuffer], { type: String(mimeType || 'image/jpeg') || 'image/jpeg' });
  const bitmap = await createImageBitmap(sourceBlob);

  const sourceCanvas = new OffscreenCanvas(bitmap.width, bitmap.height);
  const sourceContext = sourceCanvas.getContext('2d', { alpha: false, willReadFrequently: true });
  if (!sourceContext) {
    bitmap.close?.();
    throw new Error('source context unavailable');
  }
  sourceContext.drawImage(bitmap, 0, 0, sourceCanvas.width, sourceCanvas.height);
  bitmap.close?.();

  const normalizedQuad = normalizeQuad(quadNorm);
  const pixelQuad = normalizedQuad.map((point) => ({
    x: point.x * sourceCanvas.width,
    y: point.y * sourceCanvas.height
  }));

  const warpedCanvas = warpPerspective(sourceCanvas, pixelQuad, Number(maxLongEdge) || 2200);
  applyFilterToCanvas(warpedCanvas, String(filterMode || 'original'));
  const rotatedCanvas = rotateCanvasByTurns(warpedCanvas, Number(rotationTurns) || 0);

  const outputBlob = await rotatedCanvas.convertToBlob({
    type: 'image/jpeg',
    quality: 0.9
  });
  const outputBuffer = await outputBlob.arrayBuffer();

  return {
    buffer: outputBuffer,
    width: rotatedCanvas.width,
    height: rotatedCanvas.height
  };
}

function normalizeDetectionResult(raw) {
  const empty = makeEmptyDetectionResult();
  if (!raw || typeof raw !== 'object') {
    return empty;
  }

  const quad = normalizeQuad(raw.quad);
  const hasQuad = Array.isArray(raw.quad) && raw.quad.length === 4;
  const confidence = hasQuad ? clamp(Number(raw.confidence) || 0, 0, 1) : 0;

  const metricsRaw = raw.metrics && typeof raw.metrics === 'object' ? raw.metrics : {};
  const bboxRaw = metricsRaw.bbox && typeof metricsRaw.bbox === 'object' ? metricsRaw.bbox : null;

  return {
    quad: hasQuad ? quad : null,
    confidence,
    metrics: {
      areaRatio: hasQuad ? clamp(Number(metricsRaw.areaRatio) || 0, 0, 1) : 0,
      jitter: hasQuad ? clamp(Number(metricsRaw.jitter) || 0, 0, 1) : 0,
      edgeStrength: hasQuad ? clamp(Number(metricsRaw.edgeStrength) || 0, 0, 1) : 0,
      anglesScore: hasQuad ? clamp(Number(metricsRaw.anglesScore) || 0, 0, 1) : 0,
      bbox:
        hasQuad && bboxRaw
          ? {
              x: clamp(Number(bboxRaw.x) || 0, 0, 1),
              y: clamp(Number(bboxRaw.y) || 0, 0, 1),
              width: clamp(Number(bboxRaw.width) || 0, 0, 1),
              height: clamp(Number(bboxRaw.height) || 0, 0, 1)
            }
          : null
    }
  };
}

function makeEmptyDetectionResult() {
  return {
    quad: null,
    confidence: 0,
    metrics: {
      areaRatio: 0,
      jitter: 0,
      edgeStrength: 0,
      anglesScore: 0,
      bbox: null
    }
  };
}

function normalizeQuad(points) {
  const source = Array.isArray(points) ? points : [];
  if (source.length !== 4) {
    return [
      { x: 0.06, y: 0.06 },
      { x: 0.94, y: 0.06 },
      { x: 0.94, y: 0.94 },
      { x: 0.06, y: 0.94 }
    ];
  }
  return source.map((point) => ({
    x: clamp(Number(point?.x) || 0, 0.01, 0.99),
    y: clamp(Number(point?.y) || 0, 0.01, 0.99)
  }));
}

function fitSizeToLongEdge(width, height, longEdge) {
  const normalizedWidth = Math.max(1, Number(width) || 1);
  const normalizedHeight = Math.max(1, Number(height) || 1);
  const maxEdge = Math.max(normalizedWidth, normalizedHeight);
  if (maxEdge <= longEdge) {
    return { width: normalizedWidth, height: normalizedHeight };
  }
  const scale = longEdge / maxEdge;
  return {
    width: Math.max(1, Math.round(normalizedWidth * scale)),
    height: Math.max(1, Math.round(normalizedHeight * scale))
  };
}

function distance(pointA, pointB) {
  return Math.hypot((pointA?.x || 0) - (pointB?.x || 0), (pointA?.y || 0) - (pointB?.y || 0));
}

function warpPerspective(sourceCanvas, quad, maxLongEdge = 2200) {
  const widthEstimate = Math.max(distance(quad[0], quad[1]), distance(quad[3], quad[2]));
  const heightEstimate = Math.max(distance(quad[0], quad[3]), distance(quad[1], quad[2]));
  const outputSize = fitSizeToLongEdge(
    Math.max(1, Math.round(widthEstimate)),
    Math.max(1, Math.round(heightEstimate)),
    maxLongEdge
  );

  const destinationCanvas = new OffscreenCanvas(Math.max(1, outputSize.width), Math.max(1, outputSize.height));
  const srcContext = sourceCanvas.getContext('2d', { alpha: false, willReadFrequently: true });
  const dstContext = destinationCanvas.getContext('2d', { alpha: false, willReadFrequently: true });
  if (!srcContext || !dstContext) {
    return sourceCanvas;
  }

  const srcFrame = srcContext.getImageData(0, 0, sourceCanvas.width, sourceCanvas.height);
  const dstFrame = dstContext.createImageData(destinationCanvas.width, destinationCanvas.height);
  const homography = solveRectToQuadHomography(quad, destinationCanvas.width, destinationCanvas.height);
  if (!homography) {
    return sourceCanvas;
  }

  const srcPixels = srcFrame.data;
  const dstPixels = dstFrame.data;
  const srcWidth = sourceCanvas.width;
  const srcHeight = sourceCanvas.height;

  for (let y = 0; y < destinationCanvas.height; y += 1) {
    for (let x = 0; x < destinationCanvas.width; x += 1) {
      const mapped = applyHomography(homography, x, y);
      const dstOffset = (y * destinationCanvas.width + x) * 4;
      sampleBilinear(srcPixels, srcWidth, srcHeight, mapped.x, mapped.y, dstPixels, dstOffset);
    }
  }

  dstContext.putImageData(dstFrame, 0, 0);
  return destinationCanvas;
}

function applyFilterToCanvas(canvas, selectedFilter) {
  if (selectedFilter === 'original') {
    return;
  }

  const context = canvas.getContext('2d', { alpha: false, willReadFrequently: true });
  if (!context) {
    return;
  }

  const frame = context.getImageData(0, 0, canvas.width, canvas.height);
  const data = frame.data;

  if (selectedFilter === 'gray') {
    for (let i = 0; i < data.length; i += 4) {
      const gray = Math.round(data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114);
      data[i] = gray;
      data[i + 1] = gray;
      data[i + 2] = gray;
    }
    context.putImageData(frame, 0, 0);
    return;
  }

  const gray = new Uint8ClampedArray(data.length / 4);
  for (let i = 0, p = 0; i < gray.length; i += 1, p += 4) {
    gray[i] = Math.round(data[p] * 0.299 + data[p + 1] * 0.587 + data[p + 2] * 0.114);
  }

  const width = canvas.width;
  const height = canvas.height;
  const sharpened = new Uint8ClampedArray(gray.length);

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = y * width + x;
      if (x === 0 || y === 0 || x === width - 1 || y === height - 1) {
        sharpened[index] = gray[index];
        continue;
      }
      const center = gray[index] * 1.6;
      const around = (gray[index - 1] + gray[index + 1] + gray[index - width] + gray[index + width]) * 0.15;
      sharpened[index] = clamp(Math.round(center - around), 0, 255);
    }
  }

  for (let i = 0, p = 0; i < sharpened.length; i += 1, p += 4) {
    const contrasted = clamp(Math.round((sharpened[i] - 128) * 1.55 + 132), 0, 255);
    const leveled = contrasted > 242 ? 255 : contrasted;
    data[p] = leveled;
    data[p + 1] = leveled;
    data[p + 2] = leveled;
  }

  context.putImageData(frame, 0, 0);
}

function rotateCanvasByTurns(canvas, turns) {
  const normalizedTurns = ((Number(turns) || 0) % 4 + 4) % 4;
  if (normalizedTurns === 0) {
    return canvas;
  }

  const rotated = new OffscreenCanvas(
    normalizedTurns % 2 === 0 ? canvas.width : canvas.height,
    normalizedTurns % 2 === 0 ? canvas.height : canvas.width
  );

  const context = rotated.getContext('2d', { alpha: false });
  if (!context) {
    return canvas;
  }

  if (normalizedTurns === 1) {
    context.translate(rotated.width, 0);
    context.rotate(Math.PI / 2);
  } else if (normalizedTurns === 2) {
    context.translate(rotated.width, rotated.height);
    context.rotate(Math.PI);
  } else {
    context.translate(0, rotated.height);
    context.rotate(-Math.PI / 2);
  }

  context.drawImage(canvas, 0, 0);
  return rotated;
}

function solveRectToQuadHomography(quad, width, height) {
  const destination = [
    { x: 0, y: 0 },
    { x: width - 1, y: 0 },
    { x: width - 1, y: height - 1 },
    { x: 0, y: height - 1 }
  ];

  const matrix = [];
  const vector = [];

  for (let i = 0; i < 4; i += 1) {
    const dx = destination[i].x;
    const dy = destination[i].y;
    const sx = quad[i].x;
    const sy = quad[i].y;

    matrix.push([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy]);
    vector.push(sx);
    matrix.push([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy]);
    vector.push(sy);
  }

  const solution = solveLinearSystem(matrix, vector);
  if (!solution) {
    return null;
  }

  return {
    a: solution[0],
    b: solution[1],
    c: solution[2],
    d: solution[3],
    e: solution[4],
    f: solution[5],
    g: solution[6],
    h: solution[7]
  };
}

function solveLinearSystem(matrixInput, vectorInput) {
  const n = vectorInput.length;
  const matrix = matrixInput.map((row) => row.slice());
  const vector = vectorInput.slice();

  for (let col = 0; col < n; col += 1) {
    let pivot = col;
    for (let row = col + 1; row < n; row += 1) {
      if (Math.abs(matrix[row][col]) > Math.abs(matrix[pivot][col])) {
        pivot = row;
      }
    }

    if (Math.abs(matrix[pivot][col]) < 1e-10) {
      return null;
    }

    if (pivot !== col) {
      [matrix[col], matrix[pivot]] = [matrix[pivot], matrix[col]];
      [vector[col], vector[pivot]] = [vector[pivot], vector[col]];
    }

    const pivotValue = matrix[col][col];
    for (let j = col; j < n; j += 1) {
      matrix[col][j] /= pivotValue;
    }
    vector[col] /= pivotValue;

    for (let row = 0; row < n; row += 1) {
      if (row === col) {
        continue;
      }
      const factor = matrix[row][col];
      if (Math.abs(factor) < 1e-12) {
        continue;
      }
      for (let j = col; j < n; j += 1) {
        matrix[row][j] -= factor * matrix[col][j];
      }
      vector[row] -= factor * vector[col];
    }
  }

  return vector;
}

function applyHomography(h, x, y) {
  const denominator = h.g * x + h.h * y + 1;
  if (Math.abs(denominator) < 1e-8) {
    return { x: -1, y: -1 };
  }
  return {
    x: (h.a * x + h.b * y + h.c) / denominator,
    y: (h.d * x + h.e * y + h.f) / denominator
  };
}

function sampleBilinear(srcPixels, srcWidth, srcHeight, x, y, dstPixels, dstOffset) {
  if (x < 0 || y < 0 || x > srcWidth - 1 || y > srcHeight - 1) {
    dstPixels[dstOffset] = 255;
    dstPixels[dstOffset + 1] = 255;
    dstPixels[dstOffset + 2] = 255;
    dstPixels[dstOffset + 3] = 255;
    return;
  }

  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const x1 = Math.min(srcWidth - 1, x0 + 1);
  const y1 = Math.min(srcHeight - 1, y0 + 1);
  const dx = x - x0;
  const dy = y - y0;

  const i00 = (y0 * srcWidth + x0) * 4;
  const i10 = (y0 * srcWidth + x1) * 4;
  const i01 = (y1 * srcWidth + x0) * 4;
  const i11 = (y1 * srcWidth + x1) * 4;

  for (let c = 0; c < 3; c += 1) {
    const v00 = srcPixels[i00 + c];
    const v10 = srcPixels[i10 + c];
    const v01 = srcPixels[i01 + c];
    const v11 = srcPixels[i11 + c];

    const top = v00 + (v10 - v00) * dx;
    const bottom = v01 + (v11 - v01) * dx;
    dstPixels[dstOffset + c] = Math.round(top + (bottom - top) * dy);
  }
  dstPixels[dstOffset + 3] = 255;
}

function extractQuadPoints(approxMat) {
  const raw = approxMat.data32S || [];
  const points = [];
  for (let i = 0; i < raw.length; i += 2) {
    points.push({ x: raw[i], y: raw[i + 1] });
  }
  return points;
}

function orderQuadPoints(points) {
  if (!Array.isArray(points) || points.length !== 4) {
    return null;
  }

  const bySum = points.slice().sort((a, b) => a.x + a.y - (b.x + b.y));
  const byDiff = points.slice().sort((a, b) => a.x - a.y - (b.x - b.y));

  const topLeft = bySum[0];
  const bottomRight = bySum[3];
  const topRight = byDiff[3];
  const bottomLeft = byDiff[0];

  return [topLeft, topRight, bottomRight, bottomLeft];
}

function fitLineYFromX(samples) {
  let sx = 0;
  let sy = 0;
  let sxy = 0;
  let sxx = 0;
  for (const point of samples) {
    sx += point.x;
    sy += point.y;
    sxy += point.x * point.y;
    sxx += point.x * point.x;
  }
  const n = samples.length;
  const denominator = n * sxx - sx * sx;
  if (Math.abs(denominator) < 1e-6) {
    return null;
  }
  const a = (n * sxy - sx * sy) / denominator;
  const b = (sy - a * sx) / n;
  return { a, b };
}

function fitLineXFromY(samples) {
  let sx = 0;
  let sy = 0;
  let sxy = 0;
  let syy = 0;
  for (const point of samples) {
    sx += point.x;
    sy += point.y;
    sxy += point.x * point.y;
    syy += point.y * point.y;
  }
  const n = samples.length;
  const denominator = n * syy - sy * sy;
  if (Math.abs(denominator) < 1e-6) {
    return null;
  }
  const a = (n * sxy - sx * sy) / denominator;
  const b = (sx - a * sy) / n;
  return { a, b };
}

function intersectLines(lineY, lineX) {
  const denominator = 1 - lineY.a * lineX.a;
  if (Math.abs(denominator) < 1e-6) {
    return { x: 0, y: 0 };
  }
  const y = (lineY.a * lineX.b + lineY.b) / denominator;
  const x = lineX.a * y + lineX.b;
  return { x, y };
}

function polygonArea(points) {
  let area = 0;
  for (let i = 0; i < points.length; i += 1) {
    const current = points[i];
    const next = points[(i + 1) % points.length];
    area += current.x * next.y - next.x * current.y;
  }
  return Math.abs(area) * 0.5;
}

function boundingBox(points) {
  let minX = Number.POSITIVE_INFINITY;
  let maxX = Number.NEGATIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxY = Number.NEGATIVE_INFINITY;
  for (const point of points) {
    minX = Math.min(minX, point.x);
    maxX = Math.max(maxX, point.x);
    minY = Math.min(minY, point.y);
    maxY = Math.max(maxY, point.y);
  }
  return { minX, maxX, minY, maxY };
}

function computeAngleScore(quad) {
  const angles = [];
  for (let i = 0; i < 4; i += 1) {
    const prev = quad[(i + 3) % 4];
    const current = quad[i];
    const next = quad[(i + 1) % 4];
    const v1x = prev.x - current.x;
    const v1y = prev.y - current.y;
    const v2x = next.x - current.x;
    const v2y = next.y - current.y;

    const len1 = Math.hypot(v1x, v1y);
    const len2 = Math.hypot(v2x, v2y);
    if (len1 <= 1e-5 || len2 <= 1e-5) {
      return 0;
    }

    const cos = clamp((v1x * v2x + v1y * v2y) / (len1 * len2), -1, 1);
    const angle = (Math.acos(cos) * 180) / Math.PI;
    const diff = Math.abs(90 - angle);
    angles.push(clamp(1 - diff / 20, 0, 1));
  }

  if (angles.length <= 0) {
    return 0;
  }
  return angles.reduce((sum, value) => sum + value, 0) / angles.length;
}

function computeEdgeStrengthFromGradient(gradient, width, height, quad, threshold) {
  const samplesPerEdge = 18;
  let total = 0;
  let count = 0;
  for (let i = 0; i < 4; i += 1) {
    const start = quad[i];
    const end = quad[(i + 1) % 4];
    for (let s = 0; s <= samplesPerEdge; s += 1) {
      const t = s / samplesPerEdge;
      const x = Math.round(start.x + (end.x - start.x) * t);
      const y = Math.round(start.y + (end.y - start.y) * t);
      if (x < 0 || y < 0 || x >= width || y >= height) {
        continue;
      }
      total += gradient[y * width + x];
      count += 1;
    }
  }
  if (count <= 0) {
    return 0;
  }
  const meanEdge = total / count;
  return clamp(meanEdge / Math.max(1, threshold * 1.4), 0, 1);
}

function computeEdgeStrengthFromMap(edgeMap, width, height, quad) {
  const samplesPerEdge = 18;
  let total = 0;
  let count = 0;
  for (let i = 0; i < 4; i += 1) {
    const start = quad[i];
    const end = quad[(i + 1) % 4];
    for (let s = 0; s <= samplesPerEdge; s += 1) {
      const t = s / samplesPerEdge;
      const x = clamp(Math.round(start.x + (end.x - start.x) * t), 0, width - 1);
      const y = clamp(Math.round(start.y + (end.y - start.y) * t), 0, height - 1);
      total += edgeMap.ucharAt(y, x);
      count += 1;
    }
  }
  if (count <= 0) {
    return 0;
  }
  return clamp((total / count) / 255, 0, 1);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
