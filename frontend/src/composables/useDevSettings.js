import { readonly, ref } from 'vue';

const isDev = import.meta.env.DEV;
const STORAGE_KEY = 'pm.dev.preferences.v1';
const defaults = Object.freeze({
  showEnvironmentIndicator: true,
  showOnboardingLauncher: true,
  autoOpenOnboarding: false,
});

function loadPreferences() {
  const result = { ...defaults };
  if (!isDev) return result;
  try {
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY));
    for (const key of Object.keys(defaults)) {
      if (typeof stored?.[key] === 'boolean') result[key] = stored[key];
    }
  } catch { /* Fehlende oder beschädigte Browserdaten verwenden die Defaults. */ }
  return result;
}

// Bewusst browserlokal und getrennt von den synchronisierten Nutzereinstellungen.
const preferences = ref(loadPreferences());
const storageAvailable = ref(true);
const publicPreferences = readonly(preferences);

function persist() {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences.value));
    storageAvailable.value = true;
  } catch {
    storageAvailable.value = false;
  }
}

export function useDevSettings() {
  function setPreference(key, value) {
    if (!isDev || !Object.hasOwn(defaults, key) || typeof value !== 'boolean') return;
    preferences.value = { ...preferences.value, [key]: value };
    persist();
  }

  function resetPreferences() {
    if (!isDev) return;
    preferences.value = { ...defaults };
    persist();
  }

  return {
    preferences: publicPreferences,
    storageAvailable: readonly(storageAvailable),
    setPreference,
    resetPreferences,
  };
}
