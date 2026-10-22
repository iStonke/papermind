// PDF fallback must honour the same colour choice as server previews. Pure
// pixel conversion also works on WebKit versions without Canvas.filter.
export function convertImportPreviewPixels(pixels, mode) {
  if (!['grayscale', 'bw'].includes(mode)) return pixels;
  for (let index = 0; index < pixels.length; index += 4) {
    const luminance = Math.round(pixels[index] * .299 + pixels[index + 1] * .587 + pixels[index + 2] * .114);
    const value = mode === 'bw' ? luminance >= 128 ? 255 : 0 : luminance;
    pixels[index] = pixels[index + 1] = pixels[index + 2] = value;
  }
  return pixels;
}
