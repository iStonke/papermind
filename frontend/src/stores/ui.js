import { defineStore } from 'pinia';

/**
 * Kleiner UI-Store für app-weite Overlays, die von verschiedenen Stellen
 * gesteuert werden – aktuell der globale Einstellungen-Dialog. So kann z. B.
 * der ActivityIndicator (in der DocumentsView) den Dialog auf dem Backup-Tab
 * öffnen, ohne Props durch mehrere Ebenen zu reichen.
 */
export const useUiStore = defineStore('ui', {
  state: () => ({
    settingsOpen: false,
    settingsCategory: 'appearance',
    // Konto-Dialog (Profil + ggf. Benutzerverwaltung), global gemountet, damit
    // das Konto-Menü auf jeder Route funktioniert – analog zum Settings-Dialog.
    accountOpen: false,
    accountTab: 'profile',
    // Wird hochgezählt, wenn der (global gemountete) SettingsDialog ein
    // reload-imports auslöst. Die DocumentsView beobachtet diesen Zähler und
    // lädt dann ihre Dokument-/Sidebar-Daten neu.
    importsReloadSignal: 0,
  }),
  actions: {
    openSettings(category = 'appearance') {
      this.settingsCategory = category || 'appearance';
      this.settingsOpen = true;
    },
    closeSettings() {
      this.settingsOpen = false;
    },
    openAccount(tab = 'profile') {
      this.accountTab = tab || 'profile';
      this.accountOpen = true;
    },
    closeAccount() {
      this.accountOpen = false;
    },
    signalImportsReload() {
      this.importsReloadSignal += 1;
    },
  },
});
