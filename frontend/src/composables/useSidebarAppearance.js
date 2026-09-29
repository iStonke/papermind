import { ref } from 'vue';

const STORAGE_KEY = 'pm.lightSidebar';
function loadPreference() {
  try { return localStorage.getItem(STORAGE_KEY) !== 'false'; }
  catch { return true; }
}
const lightSidebar = ref(loadPreference());
// Fokusmodi (z. B. Nachbereiten) färben die Seitenleiste vorübergehend dunkel, ohne die Einstellung zu ändern.
const nightSidebar = ref(false);
export function useSidebarAppearance() {
  function setLightSidebar(value) {
    lightSidebar.value = Boolean(value);
    try { localStorage.setItem(STORAGE_KEY, String(lightSidebar.value)); } catch { /* Session preference still works. */ }
  }
  function setNightSidebar(value) { nightSidebar.value = Boolean(value); }
  return { lightSidebar, setLightSidebar, nightSidebar, setNightSidebar };
}
