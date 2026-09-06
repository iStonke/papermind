import { noteMarkdownToTipTap } from './noteMarkdown.js';

function requestsTasks(instruction) {
  const text = String(instruction || '');
  if (/\b(?:ohne|keine?)\s+(?:aufgaben|checkboxen|checkliste)|\b(?:als|nur)\s+(?:fließtext|fliesstext|absatz|tabelle)\b/i.test(text)) return false;
  return /\b(?:einkaufs(?:liste|zettel)|packliste|checkliste|aufgabenliste|to[ -]?do(?:s|[ -]?liste)?|shopping list|checklist)\b|\b(?:als|mit)\s+(?:aufgaben|checkboxen)\b/i.test(text);
}

/** Use native nodes; tolerate models that use ordinary bullets for a checklist. */
export function noteAIContent(text, { instruction = '', attribution = null } = {}) {
  const content = noteMarkdownToTipTap(text);
  if (requestsTasks(instruction)) {
    const convertLists = (nodes) => nodes.forEach((node) => {
      if (node.type === 'bulletList' || node.type === 'orderedList') {
        node.type = 'taskList';
        delete node.attrs;
        node.content.forEach((item) => { item.type = 'taskItem'; item.attrs = { checked: false }; });
      }
      if (node.content) convertLists(node.content);
    });
    convertLists(content);
    const hasTasks = (nodes) => nodes.some((node) => node.type === 'taskList' || (node.content && hasTasks(node.content)));
    if (!hasTasks(content)) {
      throw new Error('Die KI hat keine Aufgabenliste geliefert. Bitte erneut generieren.');
    }
  }
  if (attribution) content.forEach((node) => { node.attrs = { ...node.attrs, aiGeneration: attribution }; });
  return content;
}
