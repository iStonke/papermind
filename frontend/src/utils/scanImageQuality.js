/** Conservative review hints, never automatic deletion or content correction. */
export function scanImageQuality({ data, width, height }) {
  let dark = 0;
  let light = 0;
  let intensitySum = 0;
  let squaredSum = 0;
  const step = Math.max(1, Math.floor(Math.max(width, height) / 240));
  let samples = 0;
  const points = [];
  let border = 0;
  let borderDark = 0;
  for (let y = 0; y < height; y += step) for (let x = 0; x < width; x += step) {
    const index = (y * width + x) * 4;
    const intensity = (data[index] + data[index + 1] + data[index + 2]) / 3;
    intensitySum += intensity;
    squaredSum += intensity * intensity;
    if (intensity < 200) dark += 1;
    if (intensity < 160) points.push([x / step, y / step]);
    if (x < step * 2 || y < step * 2 || x >= width - step * 2 || y >= height - step * 2) {
      border++;
      if (intensity < 160) borderDark++;
    }
    if (intensity > 245) light += 1;
    samples += 1;
  }
  if (!samples) return '';
  if (dark / samples < 0.0005 && light / samples > .995) return 'Möglicherweise leer – bitte prüfen';
  const deviation = Math.sqrt(Math.max(0, squaredSum / samples - (intensitySum / samples) ** 2));
  if (dark / samples > .02 && deviation < 15) return 'Geringer Kontrast – bitte Lesbarkeit prüfen';
  if (points.length > 30 && dark / samples < .35) {
    const score = angle => {
      const rows = new Map();
      const slope = Math.tan(angle * Math.PI / 180);
      for (const [x, y] of points) {
        const row = Math.round(y + slope * x);
        rows.set(row, (rows.get(row) || 0) + 1);
      }
      return [...rows.values()].reduce((sum, count) => sum + count * count, 0);
    };
    const baseline = score(0);
    let best = baseline;
    let bestAngle = 0;
    for (let angle = -6; angle <= 6; angle++) {
      const value = score(angle);
      if (value > best) { best = value; bestAngle = angle; }
    }
    if (Math.abs(bestAngle) >= 2 && best > baseline * 1.5) return 'Möglicherweise schief – bitte Ausrichtung prüfen';
    if (border && borderDark / border > .2) return 'Möglicherweise am Rand abgeschnitten – bitte prüfen';
  }
  return '';
}
