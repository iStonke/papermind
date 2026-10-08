// Integrated templates are application definitions, never deletable database rows.
export const LECTURE_START_ID = 'builtin:lecture-start';
export const BUILTIN_START_TEMPLATES = Object.freeze([
  Object.freeze({ id: LECTURE_START_ID, title: 'Vorlesungsmitschrift', builtin: true, previewKind: 'lecture', description: 'Screenshots und Mitschrift nebeneinander' }),
]);
export const isBuiltinTemplate = id => id === LECTURE_START_ID;
