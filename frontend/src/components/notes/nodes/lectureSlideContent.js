export function lectureSlideJSON(imageAttrs = null) {
  return {
    type: 'lectureSlide',
    content: [
      { type: 'lectureSlideMedia', content: imageAttrs ? [{ type: 'image', attrs: imageAttrs }] : [] },
      { type: 'lectureSlideNotes', content: [{ type: 'paragraph' }] },
    ],
  };
}
