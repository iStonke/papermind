/** Coordinate dismissal without sharing feature state between controllers. */
export function createNoteOverlayCoordinator() {
  const closers = new Map();
  return {
    register(name, close) { closers.set(name, close); },
    open(name) {
      for (const [other, close] of closers) if (other !== name) close();
    },
    closeAll() { for (const close of closers.values()) close(); },
  };
}
