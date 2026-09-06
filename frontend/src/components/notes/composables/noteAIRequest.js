// Optional provider override for the isolated development harness.
export const NOTE_AI_STREAM = Symbol('note-ai-stream');

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
