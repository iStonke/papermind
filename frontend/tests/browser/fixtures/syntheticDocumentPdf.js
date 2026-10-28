export function syntheticDocumentPdf() {
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [4 0 R 6 0 R] /Count 2 >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
  ];
  for (const [index, width, height] of [[0, 595, 842], [1, 842, 595]]) {
    const stream = `0.12 0.22 0.24 rg BT /F1 12 Tf 42 ${height - 50} Td (NORDLICHT AKADEMIE) Tj ET\nBT /F1 24 Tf 42 ${height - 120} Td (Teilnahmebestaetigung) Tj ET\nBT /F1 12 Tf 42 ${height - 152} Td (Workshop Gestaltung und Kommunikation) Tj ET\n0.8 G 42 ${height - 185} m ${width - 42} ${height - 185} l S\nBT /F1 11 Tf 42 42 Td (28.10.2026 - Seite ${index + 1}) Tj ET`;
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${width} ${height}] /Resources << /Font << /F1 3 0 R >> >> /Contents ${5 + index * 2} 0 R >>`);
    objects.push(`<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
  }
  let pdf = '%PDF-1.4\n';
  const offsets = [0];
  objects.forEach((object, i) => { offsets.push(pdf.length); pdf += `${i + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  pdf += offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('');
  return pdf + `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
}
