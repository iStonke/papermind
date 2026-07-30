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
    settingsCategory: '',
    // Konto-Dialog (Profil + ggf. Benutzerverwaltung), global gemountet, damit
    // das Konto-Menü auf jeder Route funktioniert – analog zum Settings-Dialog.
    accountOpen: false,
    accountTab: 'profile',
    // Command-Palette (⌘K): global gemountetes Overlay, von überall per
    // Tastenkürzel auf-/zuschaltbar. Zustand hier, damit jede Route ihn steuern
    // kann – analog zu settingsOpen/accountOpen.
    paletteOpen: false,
    // Wird hochgezählt, wenn der (global gemountete) SettingsDialog ein
    // reload-imports auslöst. Die DocumentsView beobachtet diesen Zähler und
    // lädt dann ihre Dokument-/Sidebar-Daten neu.
    importsReloadSignal: 0,
  }),
  actions: {
    openSettings(category = '') {
      this.settingsCategory = category || '';
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
    openPalette() {
      this.paletteOpen = true;
    },
    closePalette() {
      this.paletteOpen = false;
    },
    togglePalette() {
      this.paletteOpen = !this.paletteOpen;
    },
    signalImportsReload() {
      this.importsReloadSignal += 1;
    },
  },
});
