// Optional provider override for the isolated development harness.
export const NOTE_AI_STREAM = Symbol('note-ai-stream');
// Separate override for the structured review path (returns a JSON change list).
export const NOTE_AI_REVIEW_STREAM = Symbol('note-ai-review-stream');

/** A cancelled response must not modify a newer request, even in finally. */
export function createNoteAIRequest() {
  let active = null;
  function cancel() {
    const previous = active;
    active = null;
    previous?.abort();
  }
  return {
    cancel,
    begin() {
      cancel();
      const controller = new AbortController();
      active = controller;
      return {
        signal: controller.signal,
        isCurrent: () => active === controller && !controller.signal.aborted,
      };
    },
  };
}
