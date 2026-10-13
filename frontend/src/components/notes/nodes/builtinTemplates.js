// Integrated templates are application definitions, never deletable database rows.
export const LECTURE_START_ID = 'builtin:lecture-start';
export const BUILTIN_START_TEMPLATES = Object.freeze([
  Object.freeze({ id: LECTURE_START_ID, title: 'Mitschrift', builtin: true, previewKind: 'lecture', description: 'Bilder und Text nebeneinander' }),
]);
export const isBuiltinTemplate = id => id === LECTURE_START_ID;
