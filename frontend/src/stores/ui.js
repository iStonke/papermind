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
    // Geführter Einstieg für neue Benutzer. In der Entwicklung kann das
    // Fenster unabhängig vom Abschlussstatus jederzeit erneut geöffnet werden.
    onboardingOpen: false,
    onboardingSource: '',
    // Signale, mit denen die Palette die (lokal in DocumentsWorkspace
    // verwalteten) Views/Aktionen anstößt – analog zu importsReloadSignal.
    // Zähler statt reiner Wert, damit der Watcher auch feuert, wenn zweimal
    // hintereinander dasselbe Ziel kommt.
    pendingView: null,
    viewRequestSignal: 0,
    pendingAction: null,
    actionRequestSignal: 0,
    // Generischer Workspace-Dispatch mit Payload (Dokument öffnen, Volltext-
    // Suche, Tag-/Typ-Filter) – ebenfalls in DocumentsWorkspace verankert.
    pendingWorkspace: null,
    workspaceRequestSignal: 0,
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
    openOnboarding(source = 'manual') {
      this.onboardingSource = source || 'manual';
      this.onboardingOpen = true;
    },
    closeOnboarding() {
      this.onboardingOpen = false;
    },
    requestView(viewKey) {
      this.pendingView = viewKey || null;
      this.viewRequestSignal += 1;
    },
    requestAction(actionKey) {
      this.pendingAction = actionKey || null;
      this.actionRequestSignal += 1;
    },
    requestWorkspace(type, payload = null) {
      this.pendingWorkspace = type ? { type, payload } : null;
      this.workspaceRequestSignal += 1;
    },
    signalImportsReload() {
      this.importsReloadSignal += 1;
    },
  },
});
