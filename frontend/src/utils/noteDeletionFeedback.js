import { useNotifications } from '../stores/notifications.js';

export function notifyNoteDeleted(note, { restore, onRestored } = {}) {
  const id = note.id;
  return useNotifications().notify({
    type: 'success',
    critical: true,
    title: 'Notiz gelöscht',
    icon: 'mdi-trash-can-outline',
    message: `„${note.title?.trim() || 'Ohne Titel'}“ liegt im Papierkorb.`,
    timeoutMs: 5000,
    action: {
      label: 'Rückgängig',
      icon: 'mdi-undo',
      errorMessage: 'Die Notiz konnte nicht wiederhergestellt werden.',
      onClick: async () => {
        await restore(id);
        onRestored?.();
      },
    },
  });
}
