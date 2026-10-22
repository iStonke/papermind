<template>
  <v-menu v-model="open" :close-on-content-click="false" location="top end" :max-width="340" transition="fade-transition">
    <template #activator="{ props: activator }"><v-btn v-bind="activator" class="isd-readiness-help" icon="mdi-information-outline" size="small" variant="text" aria-label="Was fehlt für den Import?" title="Was fehlt für den Import?" /></template>
    <div class="isd-readiness-card" role="dialog" aria-label="Für den Import erforderliche Angaben" @keydown.enter.stop>
      <strong>Bitte noch ergänzen oder prüfen</strong>
      <div v-for="item in blockers" :key="item.id" class="isd-readiness-document">
        <p v-if="blockers.length > 1">{{ item.title || 'Dokument ohne Namen' }}</p>
        <button v-for="field in item.fields" :key="field.key" type="button" @click="emit('navigate', { id:item.id, field:field.key }); open = false">
          {{ field.label }}{{ field.invalid ? ' korrigieren' : ' ergänzen' }}<v-icon size="16" aria-hidden="true">mdi-arrow-right</v-icon>
        </button>
      </div>
    </div>
  </v-menu>
</template>
<script setup>
import { ref } from 'vue';
defineProps({ blockers: Array });
const emit = defineEmits(['navigate']);
const open = ref(false);
</script>
<style scoped>
.isd-readiness-card { background:rgb(var(--v-theme-surface)); color:rgb(var(--v-theme-on-surface)); border:1px solid var(--pm-divider); border-radius:12px; padding:16px; font-size:13px; max-height:360px; overflow:auto; }
.isd-readiness-document { margin-top:10px; }
.isd-readiness-document p { margin:12px 0 4px; font-weight:600; overflow-wrap:anywhere; }
.isd-readiness-document button { display:flex; align-items:center; justify-content:space-between; width:100%; min-height:36px; text-align:left; padding:6px 0; gap:12px; color:inherit; border:0; background:transparent; cursor:pointer; }
.isd-readiness-document button:focus-visible { outline:2px solid rgb(var(--v-theme-primary)); outline-offset:2px; }
@media (any-pointer:coarse) { .isd-readiness-help.v-btn, .isd-readiness-document button { min-height:44px; min-width:44px; } }
</style>
