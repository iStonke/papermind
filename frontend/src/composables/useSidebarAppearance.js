import { ref } from 'vue';

const STORAGE_KEY = 'pm.lightSidebar';
function loadPreference() {
  try { return localStorage.getItem(STORAGE_KEY) !== 'false'; }
  catch { return true; }
}
const lightSidebar = ref(loadPreference());
export function useSidebarAppearance() {
  function setLightSidebar(value) {
    lightSidebar.value = Boolean(value);
    try { localStorage.setItem(STORAGE_KEY, String(lightSidebar.value)); } catch { /* Session preference still works. */ }
  }
  return { lightSidebar, setLightSidebar };
}
