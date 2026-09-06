/** Move the exact selection, including its marks and block structure, into a callout. */
export function replaceSelectionWithCallout(tr, type, attrs) {
  const content = tr.selection.content().content;
  if (tr.selection.empty || !type.validContent(content)) return false;
  tr.replaceSelectionWith(type.create(attrs, content), false).scrollIntoView();
  return true;
}
