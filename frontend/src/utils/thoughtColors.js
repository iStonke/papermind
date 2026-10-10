export const THOUGHT_COLORS = [{ name:'Salbei',value:'#cce0dc' },{ name:'Blau',value:'#cbdff1' },{ name:'Lavendel',value:'#ded3ee' },{ name:'Rosa',value:'#efd2dc' },{ name:'Apricot',value:'#f1d6bd' },{ name:'Gelb',value:'#eee3b4' },{ name:'Grau',value:'#d9dfe2' }];

const DARK_THOUGHT_COLORS = ['#28756b', '#356fa4', '#7857a5', '#a34d72', '#965d36', '#806920', '#586b75'];
// Keep stored colors stable; only their presentation changes with the theme.
export function thoughtDisplayColor(value, dark = false) {
  const color = value || THOUGHT_COLORS[0].value;
  const index = THOUGHT_COLORS.findIndex(option => option.value === color.toLowerCase());
  return dark && index >= 0 ? DARK_THOUGHT_COLORS[index] : color;
}
