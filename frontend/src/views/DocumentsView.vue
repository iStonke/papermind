<template>
  <Suspense>
    <DocumentsWorkspace />
    <template #fallback>
      <AppLoadingScreen />
    </template>
  </Suspense>
</template>

<script setup>
import { defineAsyncComponent } from 'vue';
import AppLoadingScreen from '../components/AppLoadingScreen.vue';

// Der Router importiert diese sehr kleine Hülle statisch. Erst nachdem der
// Auth-Guard abgeschlossen ist, lädt Vue die eigentliche Arbeitsfläche nach.
// Damit bleibt der frühere Router-Boot-Deadlock ausgeschlossen, ohne den
// kompletten Dokumenten-Arbeitsbereich auf der Login-Route zu übertragen.
const DocumentsWorkspace = defineAsyncComponent(() => import('./DocumentsWorkspace.vue'));
</script>
