/**
 * Deklarative Befehls-Registry der Command-Palette.
 *
 * Jeder Befehl kennt seinen run()-Weg über bereits vorhandene App-Mechanismen:
 *   - Navigation → uiStore.requestView(viewKey)  (DocumentsWorkspace übernimmt
 *     das per selectView)
 *   - Aktionen   → uiStore.openSettings()/openAccount() bzw.
 *     uiStore.requestAction() für lokal (in DocumentsWorkspace) gehaltene Aktionen
 *
 * Suche/Ranking, Entitäts-Filter, Dokumente und Präfix-Modi folgen in Schritt 3;
 * kontextbezogene Befehle in Schritt 4.
 */

export const GROUP_LABELS = Object.freeze({
  action: 'Aktionen',
  nav: 'Springe zu',
});

export const GROUP_ORDER = Object.freeze(['action', 'nav']);

export function buildCommands({ uiStore }) {
  return [
    {
      id: 'action-import',
      group: 'action',
      label: 'Dokument importieren',
      icon: 'mdi-tray-arrow-down',
      keywords: ['import', 'importieren', 'scan', 'scannen', 'hochladen', 'upload', 'pdf', 'hinzufügen'],
      run: () => uiStore.requestAction('import'),
    },
    {
      id: 'action-settings',
      group: 'action',
      label: 'Einstellungen öffnen',
      icon: 'mdi-cog-outline',
      keywords: ['einstellungen', 'settings', 'optionen', 'konfiguration'],
      run: () => uiStore.openSettings(),
    },
    {
      id: 'action-account',
      group: 'action',
      label: 'Konto öffnen',
      icon: 'mdi-account-outline',
      keywords: ['konto', 'account', 'profil', 'benutzer'],
      run: () => uiStore.openAccount(),
    },
    {
      id: 'nav-dashboard',
      group: 'nav',
      primary: true,
      label: 'Übersicht',
      icon: 'mdi-view-dashboard-outline',
      keywords: ['übersicht', 'dashboard', 'start', 'home'],
      run: () => uiStore.requestView('dashboard'),
    },
    {
      id: 'nav-all',
      group: 'nav',
      primary: true,
      label: 'Alle Dokumente',
      icon: 'mdi-file-document-multiple-outline',
      keywords: ['alle', 'dokumente', 'bibliothek', 'library'],
      run: () => uiStore.requestView('all'),
    },
    {
      id: 'nav-imports',
      group: 'nav',
      primary: true,
      label: 'Zuletzt hinzugefügt',
      icon: 'mdi-inbox-arrow-down-outline',
      keywords: ['zuletzt', 'neu', 'imports', 'hinzugefügt'],
      run: () => uiStore.requestView('imports'),
    },
    {
      id: 'nav-untagged',
      group: 'nav',
      label: 'Ohne Tags',
      icon: 'mdi-tag-off-outline',
      keywords: ['ohne tags', 'untagged', 'ungetaggt'],
      run: () => uiStore.requestView('untagged'),
    },
    {
      id: 'nav-favorites',
      group: 'nav',
      label: 'Favoriten',
      icon: 'mdi-star-outline',
      keywords: ['favoriten', 'favorites', 'sterne', 'markiert'],
      run: () => uiStore.requestView('favorites'),
    },
    {
      id: 'nav-no-text',
      group: 'nav',
      label: 'Nicht durchsuchbar',
      icon: 'mdi-text-box-remove-outline',
      keywords: ['nicht durchsuchbar', 'ocr', 'no text', 'ohne text'],
      run: () => uiStore.requestView('no_text'),
    },
    {
      id: 'nav-trash',
      group: 'nav',
      label: 'Papierkorb',
      icon: 'mdi-trash-can-outline',
      keywords: ['papierkorb', 'trash', 'gelöscht', 'müll'],
      run: () => uiStore.requestView('trash'),
    },
    {
      id: 'nav-tags',
      group: 'nav',
      label: 'Tags',
      icon: 'mdi-tag-multiple-outline',
      keywords: ['tags', 'schlagworte', 'schlagwörter'],
      run: () => uiStore.requestView('tags'),
    },
    {
      id: 'nav-categories',
      group: 'nav',
      label: 'Dokumenttypen',
      icon: 'mdi-shape-outline',
      keywords: ['dokumenttypen', 'typen', 'kategorien', 'categories'],
      run: () => uiStore.requestView('categories'),
    },
    {
      id: 'nav-chat',
      group: 'nav',
      primary: true,
      label: 'KI-Chat',
      icon: 'mdi-robot-outline',
      keywords: ['ki-chat', 'chat', 'ki', 'ai', 'assistent'],
      run: () => uiStore.requestView('chat'),
    },
  ];
}
