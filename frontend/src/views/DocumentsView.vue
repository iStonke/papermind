<template>
  <Suspense>
    <DocumentsWorkspace />
    <template #fallback>
      <main class="documents-boot" aria-busy="true" aria-live="polite">
        Dokumente werden geladen…
      </main>
    </template>
  </Suspense>
</template>

<script setup>
import { defineAsyncComponent } from 'vue';

// Der Router importiert diese sehr kleine Hülle statisch. Erst nachdem der
// Auth-Guard abgeschlossen ist, lädt Vue die eigentliche Arbeitsfläche nach.
// Damit bleibt der frühere Router-Boot-Deadlock ausgeschlossen, ohne den
// kompletten Dokumenten-Arbeitsbereich auf der Login-Route zu übertragen.
const DocumentsWorkspace = defineAsyncComponent(() => import('./DocumentsWorkspace.vue'));
</script>

<style scoped>
.documents-boot {
  display: grid;
  min-height: 100dvh;
  place-items: center;
  color: rgb(var(--v-theme-on-surface-variant, 78 79 86));
  font-size: 0.9rem;
}
</style>
