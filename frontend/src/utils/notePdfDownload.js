import { noteExportFilename } from './noteExport.js';

/** Render the existing print layout locally, then download actual PDF bytes. */
export async function downloadNotePdf(html, title) {
  const { default: html2pdf } = await import('html2pdf.js');
  const parsed = new DOMParser().parseFromString(html, 'text/html');
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(parsed.querySelector('style')?.textContent || '');
  const scope = 'pm-note-pdf-document';
  const styles = [...sheet.cssRules].filter(rule => rule.type === CSSRule.STYLE_RULE).map(rule => {
    const selectors = rule.selectorText.split(',').map(selector => {
      const trimmed = selector.trim();
      return trimmed === 'body' ? `.${scope}` : `.${scope} ${trimmed}`;
    }).join(', ');
    return `${selectors} { ${rule.style.cssText} }`;
  }).join('\n');
  const source = document.createElement('div');
  source.className = scope;
  const style = document.createElement('style');
  style.textContent = `${styles}\n.${scope} { background: white; width: 166mm; }\n.${scope} footer { position: static; margin-top: 10mm; }`;
  source.append(style, ...[...parsed.body.childNodes].map(node => document.importNode(node, true)));
  // The worker mounts a temporary rendering container and removes it afterwards.
  const worker = html2pdf().set({
    margin: [20, 22, 20, 22],
    filename: noteExportFilename(title).replace(/\.md$/i, '.pdf'),
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true, logging: false, backgroundColor: '#ffffff' },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait', compress: true },
    pagebreak: { mode: ['css', 'legacy'], avoid: ['tr', 'img'] },
  }).from(source);
  try {
    await worker.save();
  } finally {
    // Also clean up when an image or the renderer fails.
    const overlay = await worker.get('overlay');
    overlay?.remove();
  }
}
