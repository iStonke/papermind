import { THOUGHT_COLORS } from './thoughtColors.js';
const titleCompare = new Intl.Collator('de', { sensitivity: 'base', numeric: true });
function compareColors(a, b) {
  const left = (a.title_color || THOUGHT_COLORS[0].value).toLowerCase();
  const right = (b.title_color || THOUGHT_COLORS[0].value).toLowerCase();
  const index = (value) => { const rank = THOUGHT_COLORS.findIndex((color) => color.value === value); return rank < 0 ? THOUGHT_COLORS.length : rank; };
  return index(left) - index(right) || left.localeCompare(right);
}
export function sortThoughts(items, field = 'created_at', direction = 'desc') {
  const sign = direction === 'asc' ? 1 : -1;
  return [...items].sort((a, b) => {
    const order = field === 'color' ? compareColors(a, b) : field === 'title'
      ? titleCompare.compare(a.text.split('\n')[0], b.text.split('\n')[0])
      : new Date(a[field]).getTime() - new Date(b[field]).getTime();
    return sign * order || String(a.id).localeCompare(String(b.id));
  });
}
