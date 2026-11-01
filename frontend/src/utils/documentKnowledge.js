import { formatDateTime, formatDocumentDateInputFromIso } from './dates.js';

const text = value => typeof value === 'string' ? value.trim() : '';
const documentFieldLabels = ['Dokumentname', 'Dokumentdatum', 'Dokumenttyp', 'Korrespondent', 'Tags'];

export function knowledgeValues(document = {}) {
  const manual = document.flags?.manual_metadata_fields || [];
  const effective = (field, fallback) => manual.includes(field) || document[field] != null ? document[field] : fallback;
  return {
    document_type: effective('document_type', document.category || document.ai_document_type) || '',
    document_date: effective('document_date', document.ai_document_date) || '',
    sender: document.correspondent_id ? text(document.correspondent_name) : manual.includes('correspondent_id') ? '' : text(document.ai_sender),
    correspondent_id: document.correspondent_id || '',
    recipient: effective('recipient', document.ai_recipient) || '',
    amount: effective('amount', document.ai_amount) ?? null,
    currency: effective('currency', document.ai_currency) || ''
  };
}

export function knowledgeDraft(document = {}) {
  const values = knowledgeValues(document);
  return { document_type: values.document_type, document_date: values.document_date,
    correspondent_id: values.correspondent_id, recipient: values.recipient,
    amount: values.amount === null ? '' : String(values.amount).replace('.', ','), currency: values.currency };
}

export function knowledgePatch(draft, initial) {
  const patch = {};
  for (const field of ['document_type', 'document_date', 'correspondent_id', 'recipient', 'amount', 'currency']) {
    const value = String(draft[field] ?? '').trim();
    if (value === String(initial[field] ?? '').trim()) continue;
    if (field === 'amount' && value) {
      // Accept a decimal comma or point; never guess at grouping separators.
      if (!/^-?\d{1,10}([.,]\d{1,2})?$/.test(value)) throw new Error('Bitte gib einen Betrag mit höchstens zwei Nachkommastellen ein, ohne Tausendertrennzeichen.');
      patch.amount = Number(value.replace(',', '.'));
    } else if (field === 'currency' && value) {
      if (!/^[A-Za-z]{3}$/.test(value)) throw new Error('Bitte gib ein dreistelliges Währungskürzel ein, zum Beispiel EUR.');
      patch.currency = value.toUpperCase();
    } else if (field === 'document_type' && value && (value.length < 2 || value.length > 30)) {
      throw new Error('Der Dokumenttyp muss zwischen 2 und 30 Zeichen lang sein.');
    } else patch[field] = value || null;
  }
  return patch;
}

export function missingDocumentFields(document = {}) {
  const fields = [
    ['Dokumentname', text(document.display_name) || text(document.original_filename)],
    ['Dokumentdatum', text(document.document_date)],
    ['Dokumenttyp', text(document.document_type) || text(document.category)],
    ['Korrespondent', document.correspondent_id],
    ['Tags', Array.isArray(document.tags) && document.tags.length > 0]
  ];
  return fields.filter(([, filled]) => !filled).map(([label]) => label);
}

export function resolveDocumentKnowledge(document = {}, { busy = false, missingFields } = {}) {
  const values = knowledgeValues(document);
  const fields = [];
  for (const [label, value] of [
    ['Dokumenttyp', text(values.document_type)],
    ['Dokumentdatum', formatDocumentDateInputFromIso(values.document_date)],
    ['Absender', text(values.sender)],
    ['Empfänger', text(values.recipient)]
  ]) if (value) fields.push({ label, value });
  if (typeof values.amount === 'number' && Number.isFinite(values.amount)) {
    const currency = text(values.currency).toUpperCase();
    const options = /^[A-Z]{3}$/.test(currency) ? { style: 'currency', currency } : {};
    const formatter = new Intl.NumberFormat('de-DE', {
      minimumFractionDigits: 2, maximumFractionDigits: 2, ...options
    });
    fields.push({ label: 'Betrag', value: formatter.format(values.amount),
      amount: new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(values.amount),
      currency: formatter.formatToParts(values.amount).find(part => part.type === 'currency')?.value || '' });
  }
  const summary = text(document.ai_summary);
  const tags = Array.isArray(document.ai_suggested_tags)
    ? [...new Map(document.ai_suggested_tags.filter(tag => text(tag)).map(tag => [text(tag).toLowerCase(), text(tag)])).values()] : [];
  const hasResults = Boolean(fields.length || summary || tags.length);
  const state = busy ? 'running' : ['done', 'error', 'skipped'].includes(document.ai_status) ? document.ai_status : 'pending';
  const labels = { running: 'Wird ausgewertet', done: 'Abgeschlossen', error: 'Fehlgeschlagen', skipped: 'Übersprungen', pending: hasResults ? 'Ergebnisse vorhanden' : 'Noch nicht ausgewertet' };
  const messages = {
    running: hasResults ? 'Die Auswertung läuft. Bis zum Abschluss siehst du die zuletzt verfügbaren Ergebnisse.' : 'Die KI wertet den Dokumenttext aus.',
    error: hasResults ? 'Die letzte Auswertung ist fehlgeschlagen. Du siehst die zuletzt verfügbaren Ergebnisse.' : 'Die KI-Auswertung konnte nicht abgeschlossen werden.',
    skipped: hasResults ? 'Die letzte Auswertung wurde übersprungen. Du siehst die zuletzt verfügbaren Ergebnisse.' : 'Für dieses Dokument wurde noch keine KI-Auswertung abgeschlossen.',
    pending: hasResults ? '' : 'Zu diesem Dokument liegt noch keine KI-Auswertung vor.',
    done: hasResults ? '' : 'Die Auswertung ist abgeschlossen, hat aber keine Angaben oder Kurzfassung geliefert.'
  };
  const processed = formatDateTime(document.ai_processed_at);
  const missing = Array.isArray(missingFields)
    ? [...new Set(missingFields.filter(field => documentFieldLabels.includes(field)))] : missingDocumentFields(document);
  const completeness = documentFieldLabels.map(label => ({ label, filled: !missing.includes(label) }));
  return {
    fields, summary, tags, hasResults, state,
    compactPrimary: ['Betrag', 'Dokumenttyp', 'Dokumentdatum'].map(label => fields.find(field => field.label === label)?.value).filter(Boolean).join(' · '),
    compactParties: [values.sender, values.recipient].filter(Boolean).join(values.sender && values.recipient ? ' → ' : ''),
    status: labels[state], message: messages[state],
    processed: processed === '-' ? '' : processed,
    processedLabel: document.ai_status === 'error' || document.ai_status === 'skipped' ? 'Letzter Versuch' : 'Letzte Auswertung',
    missing, completeness, filledCount: completeness.filter(field => field.filled).length
  };
}
