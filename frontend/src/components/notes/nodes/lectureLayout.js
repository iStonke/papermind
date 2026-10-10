/**
 * Layout einer Vorlesungsmitschrift (Wurzel-Attribut `lectureLayout`):
 *  - side    Folie neben der Mitschrift
 *  - stacked Folie über der Mitschrift
 *  - text    nur Mitschrift; Screenshots bleiben erhalten, sind aber ausgeblendet
 *
 * Ältere Notizen kennen nur das Ja/Nein-Attribut `lectureMode` (true = side).
 * Es wird weiter synchron mitgeschrieben, damit Darstellung und Einfügelogik,
 * die nur „Folie neben Mitschrift" kennen, unverändert funktionieren.
 */
export const LECTURE_LAYOUTS = Object.freeze(['side', 'stacked', 'text']);

export const LECTURE_LAYOUT_OPTIONS = Object.freeze([
  { value: 'side', title: 'Folie neben Mitschrift', icon: 'mdi-view-split-vertical' },
  { value: 'stacked', title: 'Folie über Mitschrift', icon: 'mdi-view-agenda-outline' },
  { value: 'text', title: 'Nur Mitschrift', icon: 'mdi-text-long' },
]);

export function lectureLayoutOf(attrs) {
  const layout = attrs?.lectureLayout;
  if (LECTURE_LAYOUTS.includes(layout)) return layout;
  return attrs?.lectureMode ? 'side' : 'stacked';
}

export function lectureLayoutAttrs(layout) {
  const value = LECTURE_LAYOUTS.includes(layout) ? layout : 'side';
  return { lectureLayout: value, lectureMode: value === 'side' };
}

/** CSS-Klassen am Wurzelelement von Editor und Vorschau. */
export function lectureLayoutClasses(attrs) {
  const layout = lectureLayoutOf(attrs);
  return { 'pm-lecture-mode': layout === 'side', 'pm-lecture-text': layout === 'text' };
}
